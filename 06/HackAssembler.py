import sys

class Assembler:
    def __init__(self, asm):
        self.code = Parser(asm)
        self.symbols_table = SymbolTable()

        self.assemble()

    def assemble(self):
        self.first_pass()
        self.code.line_pointer = -1
        self.second_pass()

    def first_pass(self):
        while self.code.hasMoreLines:
            self.code.advance()

            if self.code.L_INSTRACTION:
                self.add_symbol()
            
    def second_pass(self):
        hack = open(self.code.parsed_name, 'w')
        while self.code.hasMoreLines:
            self.code.advance()
            if self.code.A_INSTRACTION:
                symbol = self.code.symbol
                if not self.symbols_table.contains(symbol) and not symbol.isdigit():
                    self.symbols_table.addEntry(symbol, self.symbols_table.free)
                value = symbol if symbol.isdigit() else self.symbols_table.getAddress(symbol)
                hack.write(self.to_binary(value, 16) + '\n')
            elif self.code.C_INSTRACTION:
                value = '111' + self.code.comp + self.code.dest + self.code.jump
                hack.write(value + '\n')

        hack.close()

    def to_binary(self, number, length):
        return bin(int(number))[2:].zfill(length)

    def add_symbol(self):
        self.symbols_table.addEntry(self.code.symbol, self.code.line_pointer)
        self.code.lines.pop(self.code.line_pointer)
        self.code.line_pointer -= 1

class Parser:

    def __init__(self, asm):
        reader = open(asm, 'r')
        self.parsed_name = reader.name.replace('.asm', '.hack')
        self.lines = self._splitlines(reader)
        self.line_pointer = -1
        reader.close()

    def _splitlines(self, reader):
        content = []
        line = reader.readline()
        while line:
            comment_index = line.find('//') if line.find('//') > -1 else len(line)
            line = line[:comment_index].replace(' ', '').strip()
            if not line:
                line = reader.readline()
                continue

            content.append(line)
            line = reader.readline()


        return content

    @property
    def hasMoreLines(self):
        return self.line_pointer < len(self.lines) - 1

    def advance(self):
        self.line_pointer += 1 if self.hasMoreLines else self.line_pointer

    @property
    def currentInstruction(self):
        return self.lines[self.line_pointer]
    
    types = {
        '@': 'A_INSTRACTION',
        '(': 'L_INSTRACTION',
    }
    @property
    def instructionType(self):
        return self.types.get(self.currentInstruction[0], 'C_INSTRACTION')
    
    @property
    def symbol(self):
        if not self.A_INSTRACTION and not self.L_INSTRACTION:
            return ''
            
        return self.currentInstruction[1:].replace(')', '')

    comp_binaries = {
        '0':'0101010',  '1':'0111111',  '-1':'0111010',
        'D':'0001100', 'A':'0110000',  '!D':'0001101', '!A':'0110001', '-D':'0001111', '-A':'0110011',
        'D+1':'0011111', 'A+1':'0110111', 'D-1':'0001110', 'A-1':'0110010', 'D+A':'0000010', 'D-A':'0010011', 'A-D':'0000111', 'D&A':'0000000', 'D|A':'0010101',
        'M':'1110000', '!M':'1110001', '-M':'1110011', 'M+1':'1110111', 'M-1':'1110010', 'D+M':'1000010', 'D-M':'1010011', 'M-D':'1000111', 'D&M':'1000000', 'D|M':'1010101'
    }
    @property
    def comp(self):
        if not self.C_INSTRACTION:
            return ''

        comp = ('=' + (self.currentInstruction + ';').split(';')[0]).split('=')[-1]
        return self.comp_binaries.get(comp, '0000000')

    dest_binaries = {
        'M': '001', 'D': '010', 'A': '100',
        'DM': '011', 'MD': '011', 'AM': '101', 'MA': '101', 'AD': '110', 'DA': '110',
        'ADM': '111', 'AMD': '111', 'DAM': '111', 'DMA': '111', 'MDA': '111', 'MAD': '111'
    }
    @property
    def dest(self):
        if not self.C_INSTRACTION:
            return ''

        if self.currentInstruction.find('=') == -1:
            return '000'

        dest = (self.currentInstruction + ';').split(';')[0].split('=')[0]
        return self.dest_binaries.get(dest, '000')

    jump_binaries = {
        'JGT': '001', 'JEQ': '010', 'JGE': '011', 'JLT': '100', 'JNE': '101', 'JLE': '110', 'JMP': '111'
    }    
    @property
    def jump(self):
        if not self.C_INSTRACTION:
            return ''

        jump = (self.currentInstruction + ';').split(';')[1]
        return self.jump_binaries.get(jump, '000')

    @property
    def L_INSTRACTION(self):
        return self.instructionType == 'L_INSTRACTION'

    @property
    def C_INSTRACTION(self):
        return self.instructionType == 'C_INSTRACTION'

    @property
    def A_INSTRACTION(self):
        return self.instructionType == 'A_INSTRACTION'


class Code:
    def __init__(self):
        pass


class SymbolTable:
    def __init__(self):
        self.symbols_table = {
            'SP':0, 'LCL':1, 'ARG':2, 'THIS':3, 'THAT':4,
            'R0':0, 'R1':1, 'R2':2, 'R3':3, 'R4':4, 'R5':5, 'R6':6, 'R7':7, 'R9':9, 'R8':8, 'R10':10, 'R11':11, 'R12':12, 'R13':13, 'R14':14, 'R15':15,
            'SCREEN':0x4000, 'KBD':0x6000
        }
        self._free = 16

    @property
    def free(self):
        address = self._free
        self._free += 1
        return address
                    
    def addEntry(self, symbol, address):
        self.symbols_table[symbol] = address
        
    def contains(self, symbol):
        return symbol in self.symbols_table
        
    def getAddress(self, symbol):
        return self.symbols_table[symbol]

if __name__ == "__main__":
    asm = sys.argv[1]
    num_arg = len(sys.argv) - 1
    if num_arg != 1 or not asm.endswith('.asm'):
        print("expected 1 argument - file with .asm suffix, got {} argument/s".format(num_arg))
        sys.exit()
    assembler = Assembler(asm)