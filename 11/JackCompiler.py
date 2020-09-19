import sys
import re
import glob

OUT_PATH = ''

T_KEYWORD       = 'keyword'
T_SYM           = 'symbol'
T_NUM           = 'integerConstant'
T_STR           = 'stringConstant'
T_ID            = 'identifier'

class JackCompiler:
    def __init__(self, jacks):
        self.analyze(jacks)

    def analyze(self, jacks):
        for jack in jacks:
            CompilationEngine(jack)
            
class JackTokenizer:
    def __init__(self, jack):
        reader = open(jack, 'r')
        one_liner = self.one_liner(reader)
        self.tokens = self.tokenize(one_liner)
        self.index = -1
        reader.close()

    def one_liner(self, reader):
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
        
        one_liner = ' '.join(content)
        
        one_liner = re.sub(r'/\*(.*?)\*/', '', one_liner).strip()

        return one_liner

    def tokenize(self, one_liner):
        keywords = ['class', 'method', 'function', 'constructor', 'int', 'boolean',
                'char', 'void', 'var', 'static', 'field', 'let', 'do', 'if',
                'else', 'while', 'return', 'true', 'false', 'null', 'this']

        symbols = ['{','}','(',')','[',']','.',',',';','+','-','*','/','&','|','<','>','=','~']

        convert_symbols = {
            "<": '&lt;',
            ">": '&gt;',
            '"': '&quot;',
            "&": '&amp;',
        }

        tokens = []

        keyword_re = r'\b' + r'\b|\b'.join(keywords) + r'\b'
        sym_re = '['+re.escape(''.join(symbols))+']'
        num_re = r'\d+'
        str_re = r'"[^"\n]*"'
        id_re = r'[\w\-]+'

        word = re.compile(keyword_re+'|'+sym_re+'|'+num_re+'|'+str_re+'|'+id_re)

        types = {
            T_KEYWORD: keyword_re,
            T_SYM: sym_re,
            T_NUM: num_re,
            T_STR: str_re,
            T_ID: id_re,
        }

        split = word.findall(one_liner)

        for word in split:
            for typ, reg in types.items():
                if re.match(reg, word) != None:
                    if typ == T_STR:
                        word = word.strip('"')
                    # if typ == T_SYM:
                    #     word = convert_symbols.get(word, word)

                    tokens.append((word,typ))
                    break

        return tokens

    @property
    def hasMoreTokens(self):
        return self.index < len(self.tokens) - 1

    def advance(self):
        self.index += 1 if self.hasMoreTokens else self.index

    @property
    def currentToken(self):
        return self.tokens[self.index] if self.index > -1 else None
    
    def nextToken(self, LL):
        return self.tokens[self.index + LL] if self.hasMoreTokens else None

class CompilationEngine:
    label_count = 0
    convert_symbols = {'+':'add', '-':'sub', '*':'call Math.multiply 2', '/':'call Math.divide 2',
           '<':'lt', '>':'gt', '=':'eq', '&':'and', '|':'or'}
           
    unary_convert_symbols = {'-':'neg', '~':'not'}
    def __init__(self, jack):
        self.jackTokens = JackTokenizer(jack)
        self.vm = VMWriter(jack)
        self.symbols = SymbolTable()
        self.compileClass()
        self.vm.close()

    def process(self, expected_typ, *args):
        self.jackTokens.advance()
        val ,typ = self.jackTokens.currentToken
        if expected_typ != typ or ((expected_typ == T_KEYWORD or expected_typ == T_SYM) and val not in args):
            text = '{}, ({} {})'.format(expected_typ, typ, val)
            raise ValueError()
        
        return typ, val

    def peek(self, expected_typ, *args, LL=1):
        val, typ = self.jackTokens.nextToken(LL)
        if expected_typ != typ or ((expected_typ == T_KEYWORD or expected_typ == T_SYM) and val not in args):
            return False
        
        return True

    @property
    def label(self):
        self.label_count += 1
        return 'label{}'.format(str(self.label_count))

    def vm_variable(self, action, name):
        kind, type, index = self.symbols.kind_type_index_of(name)

        if action == 'push':
            self.vm.write_push(kind, index)
        if action == 'pop':
            self.vm.write_pop(kind, index)

    def compileClass(self):

        self.process(T_KEYWORD, 'class')
        _, self.current_class_name = self.process(T_ID)
        self.process(T_SYM, '{')
        self.compileClassVarDec()
        self.compileSubroutineDec()
        self.process(T_SYM, '}')

    def compileClassVarDec(self):
        while self.peek(T_KEYWORD, 'static', 'field'):
            _, kind = self.process(T_KEYWORD, 'static', 'field')
            _, type = self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            _, name = self.process(T_ID)
            self.symbols.append_class_table(name, type, kind)
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                _, name = self.process(T_ID)
                self.symbols.append_class_table(name, type, kind)

            self.process(T_SYM, ';')

    def compileSubroutineDec(self):
        while self.peek(T_KEYWORD, 'constructor', 'function', 'method'):
            _, self.current_subroutine_type = self.process(T_KEYWORD, 'constructor', 'function', 'method')
            _, type = self.process(T_KEYWORD, 'void', 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'void', 'int', 'char', 'boolean') else self.process(T_ID)
            _, self.current_subroutine_name = self.process(T_ID)
            self.symbols.start_subroutine()
            if self.current_subroutine_type == 'method':
                self.symbols.append_subroutine_table('this', self.current_class_name, 'argument')
            self.compileParameterList()
            self.compileSubroutineBody()

    def compileParameterList(self):
        self.process(T_SYM, '(')

        if self.peek(T_KEYWORD, 'int', 'char', 'boolean') or self.peek(T_ID):
            _, type = self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            _, name = self.process(T_ID)
            self.symbols.append_subroutine_table(name, type, 'argument')
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                _, type = self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
                _, name = self.process(T_ID)
                self.symbols.append_subroutine_table(name, type, 'argument')

        self.process(T_SYM, ')')

    def compileSubroutineBody(self):

        self.process(T_SYM, '{')
        self.compileVarDec()
        func_name = self.current_class_name+'.'+self.current_subroutine_name
        num_of_var = self.symbols.var_count('var')
        self.vm.write_function(func_name, num_of_var)
        self.this_pointer()
        self.compileStatements()
        self.process(T_SYM, '}')

    def this_pointer(self):
        if self.current_subroutine_type == 'method':
            self.vm.write_push('argument', 0)
            self.vm.write_pop('pointer', 0)
        elif self.current_subroutine_type == 'constructor':
            self.vm.write_push('constant', self.symbols.var_count('field'))
            self.vm.write_call('Memory.alloc', 1)
            self.vm.write_pop('pointer', 0)

    def compileVarDec(self):
        while self.peek(T_KEYWORD, 'var'):

            _, kind = self.process(T_KEYWORD, 'var')
            _, type = self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            _, name = self.process(T_ID)
            self.symbols.append_subroutine_table(name, type, kind)
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                _, name = self.process(T_ID)
                self.symbols.append_subroutine_table(name, type, kind)

            self.process(T_SYM, ';')

    def compileStatements(self):
        while self.peek(T_KEYWORD, 'let', 'if', 'while', 'do', 'return'):
            if self.peek(T_KEYWORD, 'let'):
                self.compileLet()
            elif self.peek(T_KEYWORD, 'if'):
                self.compileIf()
            elif self.peek(T_KEYWORD, 'while'):
                self.compileWhile()
            elif self.peek(T_KEYWORD, 'do'):
                self.compileDo()
            elif self.peek(T_KEYWORD, 'return'):
                self.compileReturn()
        
    def compileLet(self):
        self.process(T_KEYWORD, 'let')
        _, name = self.process(T_ID)
        if self.peek(T_SYM, '['):
            self.vm_variable('push', name)
            self.process(T_SYM, '[')
            self.compileExpression()
            self.process(T_SYM, ']')
            self.vm.write_arithmetic('add')
            self.process(T_SYM, '=')
            self.compileExpression()
            self.process(T_SYM, ';')
            self.vm.write_pop('temp', 1)
            self.vm.write_pop('pointer', 1)
            self.vm.write_push('temp', 1)
            self.vm.write_pop('that', 0)
            return

        self.process(T_SYM, '=')
        self.compileExpression()
        self.process(T_SYM, ';')
        self.vm_variable('pop', name)

    def compileIf(self):
        self.process(T_KEYWORD, 'if')
        label = self.label
        self.compileCondition(label)
        if self.peek(T_KEYWORD, 'else'):
            self.process(T_KEYWORD, 'else')
            self.process(T_SYM, '{')
            self.compileStatements()
            self.process(T_SYM, '}')
        self.vm.write_label(label)

    def compileWhile(self):
        self.process(T_KEYWORD, 'while')
        label = self.label
        self.vm.write_label(label)
        self.compileCondition(label)

    def compileCondition(self, label):
        self.process(T_SYM, '(')
        self.compileExpression()
        self.process(T_SYM, ')')
        self.vm.write_arithmetic('not')
        else_label = self.label
        self.vm.write_if(else_label)        
        self.process(T_SYM, '{')
        self.compileStatements()
        self.process(T_SYM, '}')
        self.vm.write_goto(label)
        self.vm.write_label(else_label)

    def compileDo(self):
        self.process(T_KEYWORD, 'do')
        self.compileSubroutineCall()
        self.vm.write_pop('temp', 0)
        self.process(T_SYM, ';')

    def compileReturn(self):
        self.process(T_KEYWORD, 'return')
        if not self.peek(T_SYM, ';'):
            self.compileExpression()
        else:
            self.vm.write_push('constant', 0)

        self.process(T_SYM, ';')
        self.vm.write_return()
        
    def compileExpression(self):
        if not self.is_term():
            return 0 

        self.compileTerm()
        while self.peek(T_SYM, '+', '-', '*', '/', '&', '|', '<', '>', '='):
            _, op = self.process(T_SYM, '+', '-', '*', '/', '&', '|', '<', '>', '=')
            self.compileTerm()
            self.vm.write_arithmetic(self.convert_symbols[op])

        return 1

    def compileTerm(self):
        
        if self.peek(T_NUM):
            _, val = self.process(T_NUM)
            self.vm.write_push('constant', val)
        elif self.peek(T_STR):
            _, string = self.process(T_STR)
            self.vm.write_push('constant', len(string))
            self.vm.write_call('String.new', 1)
            for char in string:
                self.vm.write_push('constant', ord(char))
                self.vm.write_call('String.appendChar', 2)
        elif self.peek(T_KEYWORD, 'true', 'false', 'null', 'this'):
            _, word = self.process(T_KEYWORD, 'true', 'false', 'null', 'this')
            if word == 'this':
                self.vm.write_push('pointer', 0)
            elif word == 'true':
                self.vm.write_push('constant', 1)
                self.vm.write_arithmetic('neg')
            else:
                self.vm.write_push('constant', 0)
        elif self.peek(T_SYM, '('):
            self.process(T_SYM, '(')
            self.compileExpression()
            self.process(T_SYM, ')')
        elif self.peek(T_SYM, '-', '~'):
            _, op = self.process(T_SYM, '-', '~')
            self.compileTerm()
            self.vm.write_arithmetic(self.unary_convert_symbols[op])
        elif self.peek(T_ID):
            if self.peek(T_SYM, '[', LL=2):
                _, name = self.process(T_ID)
                self.vm_variable('push', name)
                self.process(T_SYM, '[')
                self.compileExpression()
                self.process(T_SYM, ']')
                self.vm.write_arithmetic('add')
                self.vm.write_pop('pointer', 1)
                self.vm.write_push('that', 0)
            elif self.peek(T_SYM, '(', '.', LL=2):
                self.compileSubroutineCall()
            else:
                _, name = self.process(T_ID)
                self.vm_variable('push', name)

    def is_term(self):
        return (self.peek(T_NUM) or self.peek(T_STR) or 
            self.peek(T_KEYWORD, 'true', 'false', 'null', 'this') or 
            self.peek(T_ID) or self.peek(T_SYM, '(', '-', '~'))

    def compileSubroutineCall(self):
        num_of_args = 0
        _, obj_name = self.process(T_ID)
        if self.peek(T_SYM, '.'):
            self.process(T_SYM, '.')
            _, type, _ = self.symbols.kind_type_index_of(obj_name)
            
            if type:
                num_of_args += 1
                self.vm_variable('push', obj_name)
                obj_name = type

            _, func_name = self.process(T_ID)
            name = '{}.{}'.format(obj_name, func_name) 
        else:
            self.vm.write_push('pointer', 0)
            num_of_args += 1
            name = '{}.{}'.format(self.current_class_name, obj_name)
        self.process(T_SYM, '(')
        num_of_args += self.compileExpressionList()
        self.process(T_SYM, ')')
        self.vm.write_call(name, num_of_args)

    def compileExpressionList(self):

        num_of_args = self.compileExpression()

        while self.peek(T_SYM, ','):
            self.process(T_SYM, ',')
            self.compileExpression()
            num_of_args += 1

        return num_of_args

class SymbolTable:
    def __init__(self):
        self.class_table = {
            "field": [
                # {
                #     'name': 'x',
                #     'type': T_NUM,
                # },
            ],
            "static": [
                # {
                #     'name': 'x',
                #     'type': T_NUM,
                # }
            ]
        }
        self.subroutine_tables = [
            #     {
            #     "argument": [
            #         {
            #             'name': 'x',
            #             'type': T_NUM,
            #         },
            #     ],
            #     "local": [
            #         {
            #             'name': 'x',
            #             'type': T_NUM,
            #         }
            #     ]
            # }
        ]
    
    def append_class_table(self, name, type, kind):
        raw = {
            'name': name,
            'type': type,
        }
        self.class_table[kind].append(raw)
    
    def append_subroutine_table(self, name, type, kind):
        raw = {
            'name': name,
            'type': type,
        }
        self.subroutine_tables[-1][kind].append(raw)

    def start_subroutine(self):
        element = {
                "argument": [],
                "var": [],
                # "local": []
            }

        self.subroutine_tables.append(element)

    def var_count(self, kind):
        if kind in ['field', 'static']:
            count = len(self.class_table[kind]) 
        else:
            count = len(self.subroutine_tables[-1][kind])

        return count

    def kind_type_index_of(self, name):
        for kind, elements in self.class_table.items():
            for element in elements:
                if element['name'] == name:
                    return kind, element['type'], elements.index(element)
        
        for kind, elements in self.subroutine_tables[-1].items():
            for element in elements:
                if element['name'] == name:
                    return kind, element['type'], elements.index(element)

        return None, None, None

class VMWriter:
    def __init__(self, jack):
        self.file = open(jack.replace('.jack','.vm'), 'w')

    def write(self, line):
        self.file.write(line + '\n')

    def write_push(self, segment, index):
        if segment == 'field':
            segment = 'this'
        if segment == 'var':
            segment = 'local'

        line = 'push {} {}'.format(segment, str(index))
        self.write(line)

    def write_pop(self, segment, index):
        if segment == 'field':
            segment = 'this'
        if segment == 'var':
            segment = 'local'

        line = 'pop {} {}'.format(segment, str(index))
        self.write(line)

    def write_arithmetic(self, command):
        line = '{}'.format(command)
        self.write(line)

    def write_label(self, label):
        line = 'label {}'.format(label)
        self.write(line)

    def write_goto(self, label):
        line = 'goto {}'.format(label)
        self.write(line)

    def write_if(self, label):
        line = 'if-goto {}'.format(label)
        self.write(line)

    def write_call(self, name, num_of_args):
        line = 'call {} {}'.format(name, str(num_of_args))
        self.write(line)

    def write_function(self, name, num_of_locals):
        line = 'function {} {}'.format(name, str(num_of_locals))
        self.write(line)

    def write_return(self):
        line = 'return'
        self.write(line)

    def close(self):
        self.file.close()


if __name__ == "__main__":
    path_or_file = sys.argv[1]
    if not path_or_file.endswith('.jack'):
        name = path_or_file.split('\\')[-1]
        OUT_PATH = path_or_file
    
    num_of_arg = len(sys.argv) - 1
    if num_of_arg != 1:
        print("expected 1 argument - file or folder, got {} argument/s".format(num_of_arg))
        sys.exit()

    jacks = glob.glob(path_or_file+'/*.jack') or [path_or_file]
        
    if jacks == []:
        print("no jack files in folder")
        sys.exit()

    trans = JackCompiler(jacks)