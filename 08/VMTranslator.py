import sys
import os
import os.path
import glob
import re

# VM translator constants

# Command types
C_ARITHMETIC = 0
C_PUSH = 1
C_POP = 2
C_LABEL = 3
C_GOTO = 4
C_IF = 5
C_FUNCTION = 6
C_RETURN = 7
C_CALL = 8
C_ERROR = 9

# Segment names
S_LCL = 'local'
S_ARG = 'argument'
S_THIS = 'this'
S_THAT = 'that'
S_PTR = 'pointer'
S_TEMP = 'temp'
S_CONST = 'constant'
S_STATIC = 'static'
S_REG = 'reg'

# Registers
R_R0 = R_SP = 0
R_R1 = R_LCL = 1
R_R2 = R_ARG = 2
R_R3 = R_THIS = R_PTR = 3
R_R4 = R_THAT = 4
R_R5 = R_TEMP = 5
R_R6 = 6
R_R7 = 7
R_R8 = 8
R_R9 = 9
R_R10 = 10
R_R11 = 11
R_R12 = 12
R_R13 = R_FRAME = 13
R_R14 = R_RET = 14
R_R15 = R_COPY = 15

#output file name
OUT = "untitled.asm"
SYS_EXISTS = False

class VMTranslator:
    def __init__(self, vms):
        self.write_to_asm = CodeWriter()
        for vm in vms:
            self.translate(vm)
        self.write_to_asm.close_asm()

    def translate(self, vm):
        code = Parser(vm)
        self.write_to_asm.set_file_name(vm)
        while code.hasMoreLines:
            code.advance()
            command = code.commandType
            if command == C_ARITHMETIC:
                self.write_to_asm.arithmetic_command(code.arg1)
            elif command == C_PUSH or command == C_POP:
                self.write_to_asm.write_push_pop(command, code.arg1, code.arg2)
            elif command == C_LABEL:
                self.write_to_asm.label_command(code.arg1)
            elif command == C_GOTO:
                self.write_to_asm.goto_command(code.arg1)
            elif command == C_IF:
                self.write_to_asm.if_command(code.arg1)
            elif command == C_FUNCTION:
                self.write_to_asm.function_command(code.arg1, code.arg2)
            elif command == C_RETURN:
                self.write_to_asm.return_command()
            elif command == C_CALL:
                self.write_to_asm.call_command(code.arg1, code.arg2)


class Parser:
    def __init__(self, asm):
        reader = open(asm, 'r')
        self.lines = self.splitlines(reader)
        self.line_pointer = -1
        reader.close()

    def splitlines(self, reader):
        content = []
        line = reader.readline()
        while line:
            comment_index = line.find('//') if line.find('//') > -1 else len(line)
            line = line[:comment_index].strip()
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

    command_type = {
        'add': C_ARITHMETIC, 'sub': C_ARITHMETIC, 'neg': C_ARITHMETIC,
        'eq': C_ARITHMETIC, 'gt': C_ARITHMETIC, 'lt': C_ARITHMETIC,
        'and': C_ARITHMETIC, 'or': C_ARITHMETIC, 'not': C_ARITHMETIC,
        'label': C_LABEL,    'goto': C_GOTO,      'if-goto': C_IF,
        'push': C_PUSH,      'pop': C_POP,
        'call': C_CALL,      'return': C_RETURN,  'function': C_FUNCTION
    }

    @property
    def commandType(self):
        return self.command_type[self.currentInstruction.split()[0]]

    @property
    def arg1(self):
        tokens = self.currentInstruction.split()
        if len(tokens) > 1:
            return tokens[1]
        
        return tokens[0]

    @property
    def arg2(self):
        tokens = self.currentInstruction.split()
        if len(tokens) > 2:
            return int(tokens[2])
        
        return 0


class CodeWriter:
    def __init__(self):
        self.asm = open(OUT, 'w')
        self.vm = ''
        self.labelnum = 0
        self.set_file()

    def set_file(self):
        if SYS_EXISTS: 
            self.a_command('256')
            self.c_command('D', 'A')
            self.comp_to_reg(R_SP, 'D')
            self.call_command('Sys.init', 0)

    def set_file_name(self, vm):
        self.vm = vm.split('\\')[-1].replace('.vm','')

    def close_asm(self):
        self.asm.close()

    # @ command   
    def a_command(self, address):
        self.asm.write('@{}\n'.format(address))

    # dest = comp ; jump
    def c_command(self, dest, comp, jump=None):
        command = ''
        if dest:
            command += '{}='.format(dest)
        command += comp
        if jump:
            command += ';{}'.format(jump)
        self.asm.write('{}\n'.format(command))
        
    # (label)
    def l_command(self, label):
        self.asm.write('({})\n'.format(label))

    def arithmetic_command(self, command):
        if command == 'add':
            self.binary('D+A')
        elif command == 'sub':
            self.binary('A-D')
        elif command == 'neg':
            self.unary('-D')
        elif command == 'eq':
             self.compare('JEQ')
        elif command == 'gt':
             self.compare('JGT')
        elif command == 'lt':
             self.compare('JLT')
        elif command == 'and':
            self.binary('D&A')
        elif command == 'or':
             self.binary('D|A')
        elif command == 'not':
            self.unary('!D')
        
    def write_push_pop(self, command, seg, index):
        if command == C_PUSH:   self.push(seg, index)
        elif command == C_POP:  self.pop(seg, index)

    def label_command(self, label):
        self.l_command(label)
        
    def goto_command(self, label):
        self.a_command(label)              # A=label
        self.c_command(None, '0', 'JMP')   # 0;JMP
        
    def if_command(self, label):
        self.pop_to_dest('D')              # D=*SP
        self.a_command(label)              # A=label
        self.c_command(None, 'D', 'JNE')   # D;JNE
        
    def call_command(self, function_name, num_args):
        return_address = self.new_label()
        self.push(S_CONST, return_address) # push return_address
        self.push(S_REG, R_LCL)            # push LCL
        self.push(S_REG, R_ARG)            # push ARG
        self.push(S_REG, R_THIS)           # push THIS
        self.push(S_REG, R_THAT)           # push THAT
        self.load_sp_offset(-num_args-5)
        self.comp_to_reg(R_ARG, 'D')       # ARG=SP-n-5
        self.reg_to_reg(R_LCL, R_SP)       # LCL=SP
        self.a_command(function_name)      # A=function_name
        self.c_command(None, '0', 'JMP')   # 0;JMP
        self.l_command(return_address)     # (return_address)
        
    def return_command(self):
        self.reg_to_reg(R_FRAME, R_LCL)    # R_FRAME = R_LCL
        self.a_command('5')                # A=5
        self.c_command('A', 'D-A')         # A=FRAME-5
        self.c_command('D', 'M')           # D=M
        self.comp_to_reg(R_RET, 'D')       # RET=*(FRAME-5)
        self.pop(S_ARG, 0)                 # *ARG=return value
        self.reg_to_dest('D', R_ARG)       # D=ARG
        self.comp_to_reg(R_SP, 'D+1')      # SP=ARG+1
        self.prev_frame_to_reg(R_THAT)     # THAT=*(FRAME-1)
        self.prev_frame_to_reg(R_THIS)     # THIS=*(FRAME-2)
        self.prev_frame_to_reg(R_ARG)      # ARG=*(FRAME-3)
        self.prev_frame_to_reg(R_LCL)      # LCL=*(FRAME-4)
        self.reg_to_dest('A', R_RET)       # A=RET
        self.c_command(None, '0', 'JMP')   # goto RET
        
    def prev_frame_to_reg(self, reg):
        self.reg_to_dest('D', R_FRAME)     # D=FRAME
        self.c_command('D', 'D-1')         # D=FRAME-1
        self.comp_to_reg(R_FRAME, 'D')     # FRAME=FRAME-1
        self.c_command('A', 'D')           # A=FRAME-1
        self.c_command('D', 'M')           # D=*(FRAME-1)
        self.comp_to_reg(reg, 'D')         # reg=D
        
    def function_command(self, function_name, num_locals):
        self.l_command(function_name)
        for i in range(num_locals):
            self.push(S_CONST, 0)
        
    # Generate code for push and pop
    def push(self, seg, index):
        if   self.is_const_seg(seg):   self.val_to_stack(str(index))
        elif self.is_mem_seg(seg):     self.mem_to_stack(self.asm_mem_seg(seg), index)
        elif self.is_reg_seg(seg):     self.reg_to_stack(seg, index)
        elif self.is_static_seg(seg):  self.static_to_stack(seg, index)
        self.inc_sp()

    def pop(self, seg, index):
        self.dec_sp()
        if   self.is_mem_seg(seg):     self.stack_to_mem(self.asm_mem_seg(seg), index)
        elif self.is_reg_seg(seg):     self.stack_to_reg(seg, index)
        elif self.is_static_seg(seg):  self.stack_to_static(seg, index)

    def pop_to_dest(self, dest):
        self.dec_sp()
        self.stack_to_dest(dest)           # dest=*SP

    # Types of segments
    def is_mem_seg(self, seg):
        return seg in [S_LCL, S_ARG, S_THIS, S_THAT]
        
    def is_reg_seg(self, seg):
        return seg in [S_REG, S_PTR, S_TEMP]

    def is_static_seg(self, seg):
        return seg == S_STATIC

    def is_const_seg(self, seg):
        return seg == S_CONST

    # Generate code for arithmetic and logic operations.
    # Pop args off stack, perform an operation, and push the result on the stack
    def unary(self, comp):
        self.dec_sp()                      # --SP
        self.stack_to_dest('D')            # D=*SP
        self.c_command('D', comp)          # D=COMP
        self.comp_to_stack('D')            # *SP=D
        self.inc_sp()                      # ++SP
        
    def binary(self, comp):
        self.dec_sp()                      # --SP
        self.stack_to_dest('D')            # D=*SP
        self.dec_sp()                      # --SP
        self.stack_to_dest('A')            # A=*SP
        self.c_command('D', comp)          # D=comp
        self.comp_to_stack('D')            # *SP=D
        self.inc_sp()                      # ++SP

    def compare(self, jump):
        self.dec_sp()                      # --SP
        self.stack_to_dest('D')            # D=*SP
        self.dec_sp()                      # --SP
        self.stack_to_dest('A')            # A=*SP
        self.c_command('D', 'A-D')         # D=A-D
        label_eq = self.jump('D', jump)    # D;jump to label_eq
        self.comp_to_stack('0')            # *SP=0
        label_ne = self.jump('0', 'JMP')   # 0;JMP to label_ne
        self.l_command(label_eq)           # (label_eq)
        self.comp_to_stack('-1')           # *SP=-1
        self.l_command(label_ne)           # (label_ne)
        self.inc_sp()                      # ++SP

    # SP operations
    def inc_sp(self):
        self.a_command('SP')               # A=&SP
        self.c_command('M', 'M+1')         # SP=SP+1
        
    def dec_sp(self):
        self.a_command('SP')               # A=&SP
        self.c_command('M', 'M-1')         # SP=SP-1

    def load_sp(self):
        self.a_command('SP')               # A=&SP
        self.c_command('A', 'M')           # A=SP

    # Methods to store values onto the stack        
    def val_to_stack(self, val):
        self.a_command(val)                # A=val
        self.c_command('D', 'A')           # D=A
        self.comp_to_stack('D')            # *SP=D

    def reg_to_stack(self, seg, index):
        self.reg_to_dest('D', self.reg_num(seg, index))   # D=Rn
        self.comp_to_stack('D')                            # *SP=D
        
    def mem_to_stack(self, seg, index, indir=True):
        self.load_seg(seg, index, indir)   # A=seg+index
        self.c_command('D', 'M')           # D=*(seg+index)
        self.comp_to_stack('D')            # *SP=*(seg+index)

    def static_to_stack(self, seg, index):
        self.a_command(self.static_name(index))   # A=&func.#
        self.c_command('D', 'M')                   # D=func.#
        self.comp_to_stack('D')                    # *SP=func.#
        
    def comp_to_stack(self, comp):
        self.load_sp()
        self.c_command('M', comp)          # *SP=comp

    # Methods to retrieve values from the stack
    def stack_to_reg(self, seg, index):
        self.stack_to_dest('D')            # D=*SP
        self.comp_to_reg(self.reg_num(seg, index), 'D')

    def stack_to_mem(self, seg, index, indir=True):
        self.load_seg(seg, index, indir)
        self.comp_to_reg(R_COPY, 'D')      # R_COPY=D
        self.stack_to_dest('D')            # D=*SP
        self.reg_to_dest('A', R_COPY)      # A=R_COPY
        self.c_command('M', 'D')           # *(seg+index)=D

    def stack_to_static(self, seg, index):
        self.stack_to_dest('D')
        self.a_command(self.static_name(index))
        self.c_command('M', 'D')

    def stack_to_dest(self, dest):
        self.load_sp()
        self.c_command(dest, 'M')          # dest=*SP

    # Calculate SP+/-offset
    def load_sp_offset(self, offset):
        self.load_seg(self.asm_reg(R_SP), offset)

    # load address of seg+index into A and D registers
    def load_seg(self, seg, index, indir=True):
        index = index
        if index == 0:
            self.load_seg_no_index(seg, indir)
        else:
            self.load_seg_index(seg, index, indir)

    def load_seg_no_index(self, seg, indir):
        self.a_command(seg)            # A=seg
        if indir: self.indir(dest='AD')# A=D=*A

    def load_seg_index(self, seg, index, indir):
        comp = 'D+A'
        if index < 0:
            index = -index
            comp = 'A-D'
        self.a_command(str(index))     # A=index
        self.c_command('D', 'A')       # D=A
        self.a_command(seg)            # A=seg
        if indir: self.indir()         # A=*seg
        self.c_command('AD', comp)     # A=D=seg+/-index
    
    # Register ops
    def reg_to_dest(self, dest, reg):
        self.a_command(self.asm_reg(reg))  # @Rn
        self.c_command(dest, 'M')          # dest=Rn

    def comp_to_reg(self, reg, comp):
        self.a_command(self.asm_reg(reg))  # @Rn
        self.c_command('M', comp)          # Rn=comp

    def reg_to_reg(self, dest, src):
        self.reg_to_dest('D', src)
        self.comp_to_reg(dest, 'D')        # Rdest = Rsrc

    def indir(self, dest='A'):
        self.c_command(dest, 'M')
        
    def reg_num(self, seg, index):
        return self.reg_base(seg)+index
        
    def reg_base(self, seg):
        reg_base = {'reg':R_R0, 'pointer':R_PTR, 'temp':R_TEMP}
        return reg_base[seg]
        
    def static_name(self, index):
        return self.vm+'.'+str(index)
        
    # Assembler names for segments/registers
    def asm_mem_seg(self, seg):
        asm_label = {S_LCL:'LCL', S_ARG:'ARG', S_THIS:'THIS', S_THAT:'THAT'}
        return asm_label[seg]

    def asm_reg(self, regnum):
        return 'R'+str(regnum)
        
    # Jump to a new label and return the label for later definition
    def jump(self, comp, jump):
        label = self.new_label()
        self.a_command(label)              # A=label
        self.c_command(None, comp, jump)   # comp;jump
        return label
    
    # Generate a new label    
    def new_label(self):
        self.labelnum += 1
        return 'LABEL'+str(self.labelnum)
    

if __name__ == "__main__":
    path_or_file = sys.argv[1]
    if not path_or_file.endswith('.vm'):
        name = path_or_file.split('\\')[-1]
        OUT = '{}/{}.asm'.format(path_or_file, name)
    else:
        OUT = '{}.asm'.format(path_or_file).replace('.vm', '')
    num_arg = len(sys.argv) - 1
    if num_arg != 1:
        print("expected 1 argument - file or folder, got {} argument/s".format(num_arg))
        sys.exit()
    vms = glob.glob(path_or_file+'/*.vm') or [path_or_file]
    for vm in vms:
        if 'Sys.vm' in vm:
            SYS_EXISTS = True
            break
        
    if vms == []:
        print("no vm files in folder")
        sys.exit()

    trans = VMTranslator(vms)