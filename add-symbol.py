import os, re, argparse, subprocess
from pathlib import Path
import shutil

CUSTOM_LIB_NAME = "custom"
FOOTPRINTS_DIR = Path(CUSTOM_LIB_NAME + ".pretty")
MODELS_DIR = Path(CUSTOM_LIB_NAME + ".3dmodels")
SYMBOL_FILE = Path(CUSTOM_LIB_NAME + ".kicad_sym")
HEADER = "(kicad_symbol_lib\n"
HEADER2 = '\t(version 20231120)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "8.0")\n'
FOOTER = ")\n"


def extract_symbols(text):
    syms, start, depth = [], None, 0
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if "(symbol " in line and start is None:
            start, depth = i, 0
        if start is not None:
            depth += line.count("(")
            depth -= line.count(")")
            if depth == 0:
                syms.append("".join(lines[start : i + 1]))
                start = None
    return syms


def symbol_name(sym_block):
    first = sym_block.splitlines()[0]
    m = re.search(r'\(symbol\s+"([^"]+)"', first)
    if m:
        return m.group(1)
    m = re.search(r"\(symbol\s+([^\s()]+)", first)
    return m.group(1) if m else None


def read_lib_symbols(path: Path):
    if not path.exists():
        return [], set()
    data = open(path, encoding="utf-8").read()
    syms = extract_symbols(data)
    names = {symbol_name(s) for s in syms if symbol_name(s)}
    return syms, names


def merge_symbols(symbol_file: Path, symbols: list[Path]):
    existing_syms, existing_names = read_lib_symbols(symbol_file)
    added_syms, added_names, added_filenames, skipped = [], set(), set(), 0

    for f in sorted(symbols):
        if not f.suffix == ".kicad_sym":
            continue
        data = open(f, encoding="utf-8").read()
        for s in extract_symbols(data):
            nm = symbol_name(s)
            if not nm:
                continue
            if nm in existing_names or nm in added_names:
                skipped += 1
                continue
            added_syms.append(s)
            added_names.add(nm)
            added_filenames.add(f)

    with open(symbol_file, "w", encoding="utf-8") as out:
        out.write(HEADER)
        out.write(HEADER2)
        for s in existing_syms:
            out.write("\t" + s.strip() + "\n\n")
        for s in added_syms:
            out.write("\t" + s.strip() + "\n\n")
        out.write(FOOTER)

    # delete added symbols
    for added in added_filenames:
        os.unlink(added)

    print(f"Existing in symbol file: {len(existing_syms)}")
    print(f"Added: {len(added_syms)}   Skipped (dups): {skipped}")
    print(f"Output: {symbol_file}")


def easyeda2kicad(
    lcsc: str,
    symbol_file: Path,
    footprints_dir: Path,
    models_dir: Path,
) -> int:
    tmp_lib_dir = Path.cwd() / "tmp_lib"
    # name the tmp lib the same as the actual lib so the default footprint works
    tmp_symbol = tmp_lib_dir / Path(CUSTOM_LIB_NAME + ".kicad_sym")
    tmp_footprint_dir = tmp_lib_dir / Path(CUSTOM_LIB_NAME + ".pretty")
    tmp_model_dir = tmp_lib_dir / Path(CUSTOM_LIB_NAME + ".3dshapes")

    tmp_lib_dir.mkdir()

    def cleanup():
        shutil.rmtree(tmp_lib_dir, ignore_errors=True)

    retcode = subprocess.call(
        [
            "easyeda2kicad",
            "--lcsc_id",
            lcsc,
            "--full",
            "--output",
            tmp_lib_dir / CUSTOM_LIB_NAME,
            "--custom-field",
            f"LCSC:{lcsc}",
        ]
    )
    if retcode != 0:
        print(f"easyeda2kicad failed with exit code {retcode}!")
        cleanup()
        return 1

    tmp_footprint_dir
    if not tmp_symbol.exists():
        print(f"missing symbol, {tmp_symbol} does not exist")
        cleanup()
        return
    if not tmp_footprint_dir.is_dir():
        print(f"missing footprint, {tmp_footprint_dir} is not a directory")
        cleanup()
        return 1
    if not tmp_model_dir.is_dir():
        print(f"missing symbol, {tmp_model_dir} is not a directory")
        cleanup()
        return 1

    print("merging lcsc symbol with symbol file")
    merge_symbols(symbol_file, [tmp_symbol])

    print("moving footprint and model to corresponding directories")
    for footprint in tmp_footprint_dir.glob("*.kicad_mod"):
        footprint.move_into(footprints_dir)

    for model in tmp_model_dir.glob("*.step"):
        model.move_into(models_dir)

    cleanup()
    print("done!")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Append only new KiCad symbols into a target .kicad_sym",
    )
    parser.add_argument(
        "--symbol_file",
        help="Symbol file to add symbols to",
        default=SYMBOL_FILE,
        type=Path,
    )
    parser.add_argument(
        "symbols", nargs="*", help=".kicad_sym files to add to symbol file"
    )
    parser.add_argument(
        "--lcsc",
        help="If passed, uses easyeda2kicad to generate and add given LCSC part to symbol library",
    )
    parser.add_argument(
        "--footprints_dir",
        help="Directory to add footprints to",
        default=FOOTPRINTS_DIR,
        type=Path,
    )
    parser.add_argument(
        "--models_dir",
        help="Directory to add 3d models to",
        default=MODELS_DIR,
        type=Path,
    )
    args = parser.parse_args()

    if args.lcsc:
        return easyeda2kicad(
            args.lcsc, args.symbol_file, args.footprints_dir, args.models_dir
        )
    else:
        merge_symbols(args.symbol_file, args.symbols)


if __name__ == "__main__":
    exit(main())
