import sys
from types import SimpleNamespace

class Chars:
    ESC = 0x1B
    CR = 0x0D
    FF = 0x0C
    LF = 0x0A
    HT = 0x09
    CAN = 0x18
    DLE = 0x10
    SP = 0x20
    GS = 0x1D

class Color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   INVERT = '\033[7m'
   END = '\033[0m'

class Alignment:
    LEFT = 0
    CENTER = 1
    RIGHT = 2
    
ESC_COMMANDS = {
    b'@': {'name': 'init',  'arity': 0},
    b'd': {'name': 'feedl', 'arity': 1},
    b'J': {'name': 'feedp', 'arity': 1},
    b'a': {'name': 'align', 'arity': 1},
    b'7': {'name': 'heat', 'arity': 3},
    b'!': {'name': 'batchmode', 'arity': 1},
    b'E': {'name': 'emphasis', 'arity': 1},
    b'-': {'name': 'underline', 'arity': 1},
}

GS_COMMANDS = {
    b'B': {'name': 'invert', 'arity': 1},
    b'v': {'name': 'raster_image', 'arity': None}
}

def nl(output_file):
    print("", file=output_file)

def add_border(s, b):
    return "|" + b + s + b + "|";

def flush(print_state, print_settings):
    diff = print_settings.max_line_length - print_state.line_length
    match print_state.align:
        case Alignment.LEFT:
            out_line = print_state.line + " " * diff
        case Alignment.CENTER:
            diff_half = diff // 2
            extra = diff % 2
            out_line = " " * diff_half + print_state.line + " " * (diff_half + extra)
        case Alignment.RIGHT:
            out_line = " " * diff + print_state.line
        case _: out_line = print_state.line

    print(add_border(out_line, " "), file=print_settings.output_file)

    print_state.line = ''
    print_state.line_length = 0

def handle_variable_command(name, input_file, print_state, print_settings):
    input_file.read(1)
    mode = input_file.read(1)
    xL, xH = input_file.read(2)
    yL, yH = input_file.read(2)
    width = xL + xH * 256
    height = yL + yH * 256
    octets = width * height
    data = input_file.read(octets)

    rest = print_settings.max_line_length - width
    print(add_border("_" * width + " " * rest, " "),
          file=print_settings.output_file)
    for _ in range(height//8):
        print(add_border("x" * width + " " * rest, " "),
              file=print_settings.output_file)
    print(add_border("-" * width + " " * rest, " "),
          file=print_settings.output_file)


def handle_command(name, args, print_state, print_settings):
    match name:
        case 'init' | 'feedp' | 'heat' | 'batchmode':
            pass
        case 'feedl':
            lines = ord(args[0])
            for _ in range(lines):
                flush(print_state, print_settings)
        case 'emphasis':
            a0 = ord(args[0])
            if a0 % 2 == 0:
                print_state.line += Color.END
            else:
                print_state.line += Color.BOLD
        case 'underline':
            a0 = ord(args[0])
            if a0 in (0, 48):
                print_state.line += Color.END
            elif a0 in (1, 49):
                print_state.line += Color.UNDERLINE
            elif a0 in (2, 50):
                print_state.line += Color.UNDERLINE
                print_state.line += Color.RED
        case 'align':
            a0 = ord(args[0])
            if a0 in (0, 48):
                print_state.align = Alignment.LEFT
            elif a0 in (1, 49):
                print_state.align = Alignment.CENTER
            elif a0 in (2, 50):
                print_state.align = Alignment.RIGHT
        case 'invert':
            a0 = ord(args[0])
            if a0 == 0:
                print_state.line += Color.END
            else:
                print_state.line += Color.INVERT

def simulate_print(input_file, max_line_length=32, output_file=sys.stdout):
    input_file.seek(0) # Rewind

    print("\n" + add_border("`" * max_line_length, "`") , file=output_file)

    print_state = SimpleNamespace(line='', line_length=0,
                                  align=Alignment.LEFT)
    print_settings = SimpleNamespace(max_line_length=max_line_length,
                                     output_file=output_file)
    while True:
        b1 = input_file.read(1)

        # We reached end of stream
        if len(b1) == 0:
            flush(print_state, print_settings)
            break

        # Check if we have a command or special char
        match b1[0]:
            case b'\n' | Chars.LF | Chars.CR:
                flush(print_state, print_settings)
                continue
            case Chars.ESC:
                b2 = input_file.read(1)
                try:
                    name = ESC_COMMANDS[b2]['name']
                    arity = ESC_COMMANDS[b2]['arity']
                    args = [input_file.read(1) for _ in range(arity)]
                    handle_command(name, args, print_state, print_settings)
                except KeyError:
                    print(f"Unknown ESC command {b2}")
            case Chars.GS:
                b2 = input_file.read(1)
                try:
                    name = GS_COMMANDS[b2]['name']
                    arity = GS_COMMANDS[b2]['arity']
                    if arity:
                        args = [input_file.read(1) for _ in range(arity)]
                        handle_command(name, args, print_state, print_settings)
                    else:
                        handle_variable_command(name, input_file, print_state, print_settings)
                except KeyError:
                    print(f"Unknown GS command {b2}")
            case _:
                print_state.line += b1.decode()
                print_state.line_length += 1

        if (print_state.line_length == max_line_length):
            flush(print_state, print_settings)

    print(add_border("~" * max_line_length, "~") + "\n", file=output_file)

