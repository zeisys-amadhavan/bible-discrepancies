#!/usr/bin/env python3
"""
Combine multiple CSV files into one:
- Concatenates rows from all input files
- Removes duplicate rows (exact match across all columns)
- Keeps only one header row (from the first file)
- Writes result to a specified output file

Usage:
    python combine_csv.py file1.csv file2.csv file3.csv ... -o output.csv

Or with short option:
    python combine_csv.py *.csv -o combined.csv
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List


def combine_csv_files(input_files: List[Path], output_file: Path) -> None:
    """
    Combine multiple CSV files, remove duplicates, keep one header.
    """
    if not input_files:
        print("Error: No input files provided.", file=sys.stderr)
        sys.exit(1)

    # We'll store all rows here (as tuples to make them hashable)
    seen = set()
    all_rows = []
    header = None

    for file_path in input_files:
        if not file_path.is_file():
            print(f"Warning: File not found or not a file → {file_path}", file=sys.stderr)
            continue

        print(f"Reading: {file_path}")

        with file_path.open('r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)

            try:
                first_row = next(reader)
            except StopIteration:
                print(f"Warning: Empty file → {file_path}", file=sys.stderr)
                continue

            # If this is the first file with content, use its header
            if header is None:
                header = first_row
                # Add header as tuple for duplicate checking
                header_tuple = tuple(header)
                seen.add(header_tuple)
                all_rows.append(header)

            # If subsequent files have a header, skip it
            # (we assume the header is the same or at least compatible)
            is_header_row = (first_row == header)

            if not is_header_row:
                row_tuple = tuple(first_row)
                if row_tuple not in seen:
                    seen.add(row_tuple)
                    all_rows.append(first_row)

            # Process remaining rows
            for row in reader:
                row_tuple = tuple(row)
                if row_tuple not in seen:
                    seen.add(row_tuple)
                    all_rows.append(row)

    if not all_rows:
        print("No data found in any input file.", file=sys.stderr)
        sys.exit(1)

    # Write combined result
    print(f"Writing combined result to: {output_file}")
    print(f"Total unique rows (including header): {len(all_rows)}")

    with output_file.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(all_rows)


def main():
    parser = argparse.ArgumentParser(
        description="Combine multiple CSV files, remove duplicates, keep one header."
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        help="Input CSV files (can use wildcards like *.csv)"
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path("combined.csv"),
        help="Output file path (default: combined.csv)"
    )

    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        sys.exit(1)

    combine_csv_files(args.files, args.output)


if __name__ == "__main__":
    main()
