import sys

def simulate_print(input_file, output_file=sys.stdout):
    input_file.seek(0)
    line = ''
    while True:
        b = input_file.read(1)
        if len(b) == 0:
            break

        match b[0]:
            case b'\n':
                print("", file=output_file)
            case 27:
                print("ESC")
                pass

        if not b.decode().isprintable():
            continue
            
        line = line + b.decode()

        if (len(line) == 16):
            print(line, file=output_file)
            line = ''
