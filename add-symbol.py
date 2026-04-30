import os, re, argparse

SYMBOL_FILE = "symbols.kicad_sym"
HEADER  = "(kicad_symbol_lib\n"
HEADER2 = '\t(version 20231120)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "8.0")\n'
FOOTER  = ")\n"

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
                syms.append("".join(lines[start:i + 1]))
                start = None
    return syms

def symbol_name(sym_block):
    first = sym_block.splitlines()[0]
    m = re.search(r'\(symbol\s+"([^"]+)"', first)
    if m: return m.group(1)
    m = re.search(r'\(symbol\s+([^\s()]+)', first)
    return m.group(1) if m else None

def read_lib_symbols(path):
    if not os.path.exists(path): return [], set()
    data = open(path, encoding="utf-8").read()
    syms = extract_symbols(data)
    names = {symbol_name(s) for s in syms if symbol_name(s)}
    return syms, names

def merge_symbols(symbol_file, symbols: list[str]):
    existing_syms, existing_names = read_lib_symbols(symbol_file)
    added_syms, added_names, added_filenames, skipped = [], set(), set(), 0

    for f in sorted(symbols):
        if not f.endswith(".kicad_sym"): continue
        data = open(f, encoding="utf-8").read()
        for s in extract_symbols(data):
            nm = symbol_name(s)
            if not nm: continue
            if nm in existing_names or nm in added_names:
                skipped += 1
                continue
            added_syms.append(s)
            added_names.add(nm)
            added_filenames.add(f)

    with open(symbol_file, "w", encoding="utf-8") as out:
        out.write(HEADER); out.write(HEADER2)
        for s in existing_syms: out.write("\t" + s.strip() + "\n\n")
        for s in added_syms:    out.write("\t" + s.strip() + "\n\n")
        out.write(FOOTER)

    # delete added symbols
    for added in added_filenames:
        os.unlink(added)

    print(f"Existing in symbol file: {len(existing_syms)}")
    print(f"Added: {len(added_syms)}   Skipped (dups): {skipped}")
    print(f"Output: {symbol_file}")

def main():
    parser = argparse.ArgumentParser(description="Append only new KiCad symbols into a target .kicad_sym")
    parser.add_argument("--symbol_file", help="Symbol file to add symbols to", default=SYMBOL_FILE)
    parser.add_argument("symbols", nargs="+", help=".kicad_sym files to add to symbol file")
    args = parser.parse_args()
    merge_symbols(args.symbol_file, args.symbols)

if __name__ == "__main__":
    main()
