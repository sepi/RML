import sys
from math import ceil
import string
import time

# argparse is only for python 2.7
from optparse import OptionParser

# a little class for basically storing global things
class IOClass:
    def __init__(self):
        self.verbose = False
        self.dry = False
        self.port = False


def main():
    options, _ = parseArgs()

    io=IOClass()
    io.verbose=options.verbose
    io.dry=options.dry

    if options.file:
        # they want to read a file
        input_file = open(options.file)
    else:
        # we'll listen to stdin
        input_file = sys.stdin

    if options.port:
        # they want to use a serial port
        try:
            import serial
        except:
            err("serial interface not supported")
            return

        try:
            io.port = serial.serial_for_url(options.port, baudrate=options.baud)
        except IOError as error:
            err(str(error))
            err("SERIAL PORT FAIL! falling back to dry mode")
            io.dry = True

    else:
        err("no port specified. using stdout")
        io.port = sys.stdout

    parse(input_file, io)

    input_file.close()

    if not io.dry:
        io.port.close()


def print_from_file(input_file, serial_device_path):
    import serial
    with serial.Serial(serial_device_path) as ser:
        io = IOClass()
        io.port = ser
        parse(input_file, io)


def parse(input_file, io=IOClass()):
    cmdMode = False
    cmd = ""

    while True:
        if getattr(io, 'port', False) and getattr(io.port, 'in_waiting', False):
            err(io.port.read(io.port.in_waiting))

        #if not input_file.inWaiting():
        #    continue;
        c = input_file.read(1) # read 1 char

        if c == "": # EOF
            break

        # usually we want to just send the character
        #  unless we are in command mode
        #  or the c is {

        if cmdMode:
            if c == '}':
                cmdMode = False
                # end of command. time to parse it.
                handleCmd(io, cmd.strip());
                continue

            # append to cmd
            cmd=cmd+c
            continue

        if c == '{':
            # entering command mode

            cmdMode = True
            cmd=""
            continue

        # we'll allow characters 0x20 thru 0x7E and 0x0A (LF)
        # all others are ignored.
        # is that what we really want?

        if (ord(c)>=0x20 and ord(c)<=0x7E) or ord(c)==0x0A:
            # send the char! do eet!
            if ord(c)==0x0A and io.port != sys.stdout:
                time.sleep(.3)

            devSend(io, c.encode())


def parseArgs():
    parser = OptionParser()

    parser.add_option("-f", "--file", dest="file", default=False,
                      help="input file (default to stdin)", metavar="FILE")

    parser.add_option("-p", "--port", dest="port", default=False,
                      help="serial device (default to stdout)")

    parser.add_option("-b", "--baud", dest="baud", default="19200",
                      help="baud rate (default to 19200)")

    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="display extra info")

    parser.add_option("-t", "--test",
                      action="store_true", dest="dry", default=False,
                      help="don't send to serial")

#    parser.add_option("-s", "--status",
#                      action="store_true", dest="doStatus", default=False,
#                      help="show device status and exit")

    return parser.parse_args()


def handleCmd(io, command):
    # most commands map directly to device commands
    # some take arguments

    #if command=='{':
    #    devSend(io, '{')

    # the first thing is the command. Later things are arguments.
    cmd=command.split()

    valid=False

    # empty
    if len(cmd)==0:
        return

    name=cmd[0].lower()

    # commands that are directly mapped
    if name in theCommands:
        sCmd=theCommands[name]

        info(io, sCmd[1])

        devSend(io, sCmd[0])
        valid=True

    # things that take one number
    if name in oneArg:
        #info(io, "oneArg!")

        if len(cmd)==1:
            devSend(io, oneArg[name].to_bytes())
        if len(cmd)==2:
            #info(io, "arg="+str(int(cmd[1])))
            devSend(io, int(cmd[1]).to_bytes())

        valid=True

    # enlarge. This doesn't work (?)
    if name == 'e':
        h=0
        w=0
        if 'h' in command or 'H' in command:
            h=1
        if 'w' in command or 'W' in command:
            w=1

        devSend(io, chr(h*0x01 + w*0x10).encode())


    # leftSpace has special parsing
    if name == 'leftspace':
        if len(cmd)==1:
            devSend(io, int(0).to_bytes());
        if len(cmd)==2:
            devSend(io, twoBytes(int(cmd[1])));

    # barcode - more special
    if name == 'barcode':
        if len(cmd)>2:
            type=0 # type defaults to UPC-A

            if cmd[1].upper() in bcTypes:
                type=bcTypes.index(cmd[1])

            cmdSpl=command.split(' ',2)
            dat=cmdSpl[2]

            # now we want to format the data depending on the format
            
            # only number chars
            if type in [0,1,2,3,5,9,10]:
                dat="".join([c for c in dat if c in string.digits])
            
            # CODE39
            if type == 4:
                dat="".join([c for c in dat if c in CODE39chars])
            
            # CODEBAR
            if type == 6:
                dat="".join([c for c in dat if c in CODEBARchars])

            # CODE93
            if type == 7:
                pass # i'm unsure exactly what to allow. the doc suggests 0-127, 
                # but wikipedia lists a more limited set, but perhaps with
                #  special sequences for more chars?
                # mostly used by Canada Post
            
            # CODE128 - any char - use hex?
            if type == 8:
                # we want to allow for arbitary data, probably using hex,
                # but that's annoying if you just want to normals ascii text.
                # perhaps we should have an escape char for hex.
                # the questions becomes - which charachter?
                pass
            
            # code93 and code128 take binary data in range 0-127.
            # we should probably use hex input for this.
            
            # some things allow spaces: we should allow that too.
            info(io, 'barcode type='+str(type)+' data='+dat)
        
            # we'll use "format 2" syntax, with explicit length
            devSend(io, b'\x1D\x6B'+(type+65).to_bytes()+len(dat).to_bytes()+dat.encode())
            
            # I think we should wait for the data to print
    
    
    if name == 'image' or name == 'imager':
        if len(cmd)>1:
            # allows spaces in the file name
            doImage(io, command.split(' ',1)[1],(name=='imager'))

    # for raw hex
    if name[0] == 'x':
        # no other commands can start with x

        dat=command.upper();

        # remove things that aren't hex digits
        dat="".join([c for c in dat if c in string.hexdigits])

        # pad with 0 if necessary
        if len(dat)%2==1:
            dat=dat+'0'

        info(io, "raw hex: "+dat)
        devSend(io, dat)

    # so 'style' is weid.
    # the style command has 6 properties
    if name=='style':
        c=[cm.lower() for cm in cmd]

        tall='tall' in c or 'big' in c
        wide='big' in c
        inv= 'i' in c
        em = 'em' in c
        strike = 'strike' in c
        ud = 'ud' in c

        mode=(inv<<1)+(ud<<2)+(em<<3)+(tall<<4)+(wide<<5)+(strike<<6)

        devSend(io, b'\x1b\x21'+mode.to_bytes())

    # barcode text location
    if name=='bcloc':
        c=[cm.lower() for cm in cmd]

        # numbers are for backward compatibility
        above='above' in c or '1' in c or '3' in c
        below='below' in c or '2' in c or '3' in c

        loc=above*1+below*2

        devSend(io, loc.to_bytes())

    #     'heat':('\x1B\x37'    ,'heat control'),
    #  'density':('\x12\x23'    ,'density control'),

    if name=='heat':
        if len(cmd)==4:
            devSend(io, b'\x1B\x37'+int(cmd[1]).to_bytes()+int(cmd[2]).to_bytes()+int(cmd[3]).to_bytes())

    if name=='density':
        if len(cmd)==3:
            devSend(io, b'\x12\x23'+int(cmd[1]).to_bytes()+(int(cmd[2])<<4).to_bytes())


def doImage(io, path,rot):
    try:
        from PIL import Image, ImageOps
    except:
        err("please install Python Image Library")
        return

    try:
        img = Image.open(path)
    except:
        err("file "+path+" not found!")
        return

    # convert to greyscale, invert
    img=ImageOps.invert(img.convert('L'))

    if rot:
        img=img.rotate(90)

    # figure out the desired W and H
    if img.size[0]<=384:
        # if the image is less than the max,
        # round the width up to a multible of 8
        img=img.crop((0,0,int(ceil(img.size[0]/8.)*8),img.size[1]))
    else:
        # if the image is larger than the max,
        # scale it down to the max
        img=img.resize((384,img.size[1]*384//img.size[0]))


    # if verbose, show the image.
    if io.verbose:
        ImageOps.invert(img).convert('1').show()

    # stringify
    imgStr=img.convert('1').tobytes()

    info(io, path+' '+str(img.size))

    # (GS v)
    devSend(io, b'\x1D\x76\0\0'+twoBytes(img.size[0]//8)+twoBytes(img.size[1])+imgStr)

    # I think we should wait for the data to send/print
    if io.port != sys.stdout:
        time.sleep(6)

# some commands take a number (n) as two bytes (nL nH)
def twoBytes(num):
    #         low byte     high byte
    return (num%256).to_bytes()+(num//256).to_bytes()

# informative messages
# print to stderr if verbose
def info(io, s):
    if io.verbose:
        print("INFO: " + s, file=sys.stderr)

# important messages
# print to stderr
def err(s):
    print("ERROR: " + s, file=sys.stderr)

# send data to printer
def devSend(io, s):
    if not io.dry: # (wet?)
        if io.port == sys.stdout:
            io.port.buffer.write(s)
        else:
            io.port.write(s)


# commands that map directly to device commands
theCommands={
    'feedl':(b'\x1B\x64'    ,'feed (lines)'),
    'feedd':(b'\x1B\x4A'    ,'feed (dots)'),

'linespace':(b'\x1B\x33'    ,'line space'),
'leftspace':(b'\x1D\x4C'    ,'left space'),

   'left'  :(b'\x1B\x61\x00','align left'),
   'center':(b'\x1B\x61\x01','align center'),
   'right' :(b'\x1B\x61\x02','align right'),

'charspace':(b'\x1B\x20'    ,'charachter space'),

        'b':(b'\x1B\x45\x01','bold'),
       '/b':(b'\x1B\x45\x00','un-bold'),

# wide is weird. - maybe it's for special double-wide chars.
     'wide':(b'\x1B\x0B'    ,'wide'),
    '/wide':(b'\x1B\x14'    ,'un-wide'),

       'ud':(b'\x1B\x7B\x01','updown'),
      '/ud':(b'\x1B\x7B\x00','un-updown'),

      'inv':(b'\x1D\x42\x01','invert'),
     '/inv':(b'\x1D\x42\x00','un-invert'),

        'u':(b'\x1B\x2D'    ,'underline'),

        'e':(b'\x1D\x21'    ,'enlarge'),

  'charset':(b'\x1B\x52'    ,'charachter set'),
'codetable':(b'\x1B\x74'    ,'code table'),

    'bcloc':(b'\x1D\x48'    ,'barcode text location'),
      'bch':(b'\x1D\x68'    ,'barcode height'),
      'bcw':(b'\x1D\x77'    ,'barcode width'),
  'bcspace':(b'\x1D\x78'    ,'barcode left space'),

     'init':(b'\x1B\x40'    ,'initialize'),
 'testpage':(b'\x12\x54'    ,'test page'),
}

# commands that take one argument, and the default value
oneArg={
   'u':0,
   'feedl':0,
   'feedd':0,
   'linespace':0,
   'charset':0,
   'codetable':0,
#   'bcloc':0,
   'bch':50,
   'bcw':2,
   'bcspace':0,
   'charspace':0
}

# barcode types
bcTypes=[
    'UPC-A',
    'UPC-E',
    'EAN13',
    'EAN8',
    'CODE39',
    'I25',
    'CODEBAR',
    'CODE93',
    'CODE128',
    'CODE11',
    'MSI'
]

CODE39chars=string.digits+string.ascii_uppercase+' $%+'
CODEBARchars=string.digits+string.ascii_uppercase+' +'


if __name__ == '__main__':
    main()
