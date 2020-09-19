import sys
import re
import glob

OUT_PATH = ''

T_KEYWORD       = 'keyword'
T_SYM           = 'symbol'
T_NUM           = 'integerConstant'
T_STR           = 'stringConstant'
T_ID            = 'identifier'

class JackAnalyzer:
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

        keyword_re = '|'.join(keywords)
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
                    if typ == T_SYM:
                        word = convert_symbols.get(word, word)

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
    def __init__(self, jack):
        self.jackTokens = JackTokenizer(jack)
        self.xml = open(jack.replace('.jack','.xml'), 'w')
        self.compileClass()
        self.xml.close()

    def process(self, expected_typ, *args):
        self.jackTokens.advance()
        val ,typ = self.jackTokens.currentToken
        if expected_typ != typ or ((expected_typ == T_KEYWORD or expected_typ == T_SYM) and val not in args):
            text = '{}, ({} {})'.format(expected_typ, typ, val)
            raise ValueError()
        
        self.write(typ, val)

        return typ, val

    def peek(self, expected_typ, *args, LL=1):
        val, typ = self.jackTokens.nextToken(LL)
        if expected_typ != typ or ((expected_typ == T_KEYWORD or expected_typ == T_SYM) and val not in args):
            return False
        
        return True

    def write(self, typ, val):
        self.xml.write('<'+typ+'> '+ val +' </'+typ+'>\n')

    def compileClass(self):
        self.xml.write('<class>\n')

        self.process(T_KEYWORD, 'class')
        self.process(T_ID)
        self.process(T_SYM, '{')
        self.compileClassVarDec()
        self.compileSubroutineDec()
        self.process(T_SYM, '}')

        self.xml.write('</class>\n')

    def compileClassVarDec(self):
        while self.peek(T_KEYWORD, 'static', 'field'):
            self.xml.write('<classVarDec>\n')

            self.process(T_KEYWORD, 'static', 'field')
            self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            self.process(T_ID)
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                self.process(T_ID)

            self.process(T_SYM, ';')

            self.xml.write('</classVarDec>\n')

    def compileSubroutineDec(self):
        while self.peek(T_KEYWORD, 'constructor', 'function', 'method'):
            self.xml.write('<subroutineDec>\n')

            self.process(T_KEYWORD, 'constructor', 'function', 'method')
            self.process(T_KEYWORD, 'void', 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'void', 'int', 'char', 'boolean') else self.process(T_ID)
            self.process(T_ID)
            self.compileParameterList()
            self.compileSubroutineBody()

            self.xml.write('</subroutineDec>\n')

    def compileParameterList(self):
        self.process(T_SYM, '(')
        self.xml.write('<parameterList>\n')

        if self.peek(T_KEYWORD, 'int', 'char', 'boolean') or self.peek(T_ID):
            self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            self.process(T_ID)
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
                self.process(T_ID)

        self.xml.write('</parameterList>\n')
        self.process(T_SYM, ')')

    def compileSubroutineBody(self):
        self.xml.write('<subroutineBody>\n')

        self.process(T_SYM, '{')
        self.compileVarDec()
        self.compileStatements()
        self.process(T_SYM, '}')

        self.xml.write('</subroutineBody>\n')

    def compileVarDec(self):
        while self.peek(T_KEYWORD, 'var'):
            self.xml.write('<varDec>\n')

            self.process(T_KEYWORD, 'var')
            self.process(T_KEYWORD, 'int', 'char', 'boolean') if self.peek(T_KEYWORD, 'int', 'char', 'boolean') else self.process(T_ID)
            self.process(T_ID)
            while self.peek(T_SYM, ','):
                self.process(T_SYM, ',')
                self.process(T_ID)

            self.process(T_SYM, ';')

            self.xml.write('</varDec>\n')

    def compileStatements(self):
        self.xml.write('<statements>\n')

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
        
        self.xml.write('</statements>\n')

    def compileLet(self):
        self.xml.write('<letStatement>\n')

        self.process(T_KEYWORD, 'let')
        self.process(T_ID)
        if self.peek(T_SYM, '['):
            self.process(T_SYM, '[')
            self.compileExpression()
            self.process(T_SYM, ']')
        self.process(T_SYM, '=')
        self.compileExpression()
        self.process(T_SYM, ';')

        self.xml.write('</letStatement>\n')

    def compileIf(self):
        self.xml.write('<ifStatement>\n')

        self.process(T_KEYWORD, 'if')
        self.process(T_SYM, '(')
        self.compileExpression()
        self.process(T_SYM, ')')
        self.process(T_SYM, '{')
        self.compileStatements()
        self.process(T_SYM, '}')
        if self.peek(T_KEYWORD, 'else'):
            self.process(T_KEYWORD, 'else')
            self.process(T_SYM, '{')
            self.compileStatements()
            self.process(T_SYM, '}')

        self.xml.write('</ifStatement>\n')

    def compileWhile(self):
        self.xml.write('<whileStatement>\n')

        self.process(T_KEYWORD, 'while')
        self.process(T_SYM, '(')
        self.compileExpression()
        self.process(T_SYM, ')')
        self.process(T_SYM, '{')
        self.compileStatements()
        self.process(T_SYM, '}')

        self.xml.write('</whileStatement>\n')

    def compileDo(self):
        self.xml.write('<doStatement>\n')

        self.process(T_KEYWORD, 'do')
        self.compileSubroutineCall()
        self.process(T_SYM, ';')

        self.xml.write('</doStatement>\n')

    def compileReturn(self):
        self.xml.write('<returnStatement>\n')

        self.process(T_KEYWORD, 'return')
        if not self.peek(T_KEYWORD, ';'):
            self.compileExpression()

        self.process(T_SYM, ';')
        
        self.xml.write('</returnStatement>\n')

    def compileExpression(self):
        if not self.is_term():
            return

        self.xml.write('<expression>\n')

        self.compileTerm()
        while self.peek(T_SYM, '+', '-', '*', '/', '&amp;', '|', '&lt;', '&gt;', '='):
            self.process(T_SYM, '+', '-', '*', '/', '&amp;', '|', '&lt;', '&gt;', '=')
            self.compileTerm()

        self.xml.write('</expression>\n')

    def compileTerm(self):
        
        self.xml.write('<term>\n')

        if self.peek(T_NUM):
            self.process(T_NUM)
        elif self.peek(T_STR):
            self.process(T_STR)
        elif self.peek(T_KEYWORD, 'true', 'false', 'null', 'this'):
            self.process(T_KEYWORD, 'true', 'false', 'null', 'this')
        elif self.peek(T_SYM, '('):
            self.process(T_SYM, '(')
            self.compileExpression()
            self.process(T_SYM, ')')
        elif self.peek(T_SYM, '-', '~'):
            self.process(T_SYM, '-', '~')
            self.compileTerm()
        elif self.peek(T_ID):
            if self.peek(T_SYM, '[', LL=2):
                self.process(T_ID)
                self.process(T_SYM, '[')
                self.compileExpression()
                self.process(T_SYM, ']')
            elif self.peek(T_SYM, '(', '.', LL=2):
                self.compileSubroutineCall()
            else:
                self.process(T_ID)

        self.xml.write('</term>\n')

    def is_term(self):
        return (self.peek(T_NUM) or self.peek(T_STR) or 
            self.peek(T_KEYWORD, 'true', 'false', 'null', 'this') or 
            self.peek(T_ID) or self.peek(T_SYM, '(', '-', '~'))

    def compileSubroutineCall(self):
        self.process(T_ID)
        if self.peek(T_SYM, '('):
            self.process(T_SYM, '(')
            self.compileExpressionList()
            self.process(T_SYM, ')')
        elif self.peek(T_SYM, '.'):
            self.process(T_SYM, '.')
            self.process(T_ID)
            self.process(T_SYM, '(')
            self.compileExpressionList()
            self.process(T_SYM, ')')

    def compileExpressionList(self):
        self.xml.write('<expressionList>\n')

        self.compileExpression()
        while self.peek(T_SYM, ','):
            self.process(T_SYM, ',')
            self.compileExpression()

        self.xml.write('</expressionList>\n')


if __name__ == "__main__":
    path_or_file = sys.argv[1]
    if not path_or_file.endswith('.jack'):
        name = path_or_file.split('\\')[-1]
        OUT_PATH = path_or_file
    
    num_arg = len(sys.argv) - 1
    if num_arg != 1:
        print("expected 1 argument - file or folder, got {} argument/s".format(num_arg))
        sys.exit()

    jacks = glob.glob(path_or_file+'/*.jack') or [path_or_file]
        
    if jacks == []:
        print("no jack files in folder")
        sys.exit()

    trans = JackAnalyzer(jacks)