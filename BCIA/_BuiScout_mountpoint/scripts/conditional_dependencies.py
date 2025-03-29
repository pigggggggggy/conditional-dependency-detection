import csv
import sys

def calculate_related_options(csv_file):
    total_rows = 0
    non_empty_rows = 0

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            if row.get('related_options', '').strip():
                non_empty_rows += 1

    if total_rows > 0:
        ratio = non_empty_rows / total_rows
    else:
        ratio = 0

    print(f"Non-empty related_options: {non_empty_rows}")
    print(f"Percentage: {ratio * 100:.2f}%")

if __name__ == '__main__':
    csv_file = sys.argv[1]
    calculate_related_options(csv_file)
