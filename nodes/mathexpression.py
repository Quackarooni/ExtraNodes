# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN, Andrew Stevenson
#
# SPDX-License-Identifier: GPL-2.0-or-later


#How does it works?
# 1- Find the variables or constants with regex
# 2- dynamically remove/create sockets accordingly
# 3- transform the algebric expression into 'function expressions' using 'transform_expression'
# 4- execute the function expression with 'NodeSetter' using exec(), which will set the nodes in place.


import bpy 

import re, ast
from functools import partial

from ..__init__ import get_addon_prefs
from .boiler import create_new_nodegroup, create_socket, remove_socket, link_sockets, replace_node


NODE_Y_OFFSET = 120
NODE_X_OFFSET = 70
SUPERSCRIPTS = {
    '⁰': '0',
    '¹': '1',
    '²': '2',
    '³': '3',
    '⁴': '4',
    '⁵': '5',
    '⁶': '6',
    '⁷': '7',
    '⁸': '8',
    '⁹': '9',
}
IRRATIONALS = {
    'Pi':   {'unicode':'π', 'value':'3.1415927'},
    'eNum': {'unicode':'𝑒', 'value':'2.7182818'},
    'Gold': {'unicode':'φ', 'value':'1.6180339'},
}

def match_exact_tokens(string:str, tokenlist:list):
    """
    Get a list of matching token, if any token in our token list match in our string list

    A token is matched exactly:
      - For numbers (integer/float), it won't match if the token is part of a larger number.
      - For alphabetic tokens, word boundaries are used.
    """
    def build_token_pattern(tokens):
        def boundary(token):
            # For numbers, ensure the token isn't part of a larger number.
            if re.fullmatch(r'\d+(?:\.\d+)?', token):
                return r'(?<![\d.])' + re.escape(token) + r'(?![\d.])'
            else:
                # For alphabetic tokens, use word boundaries.
                return r'\b' + re.escape(token) + r'\b'
        return '|'.join(boundary(token) for token in tokens)
    
    pattern = build_token_pattern(tokenlist)
    return re.findall(pattern, string)


def replace_exact_tokens(string:str, tokens_mapping:dict):
    """Replace any token in the given string with new values as defined by the tokens_mapping dictionary."""
    
    def build_token_pattern(tokens):
        def boundary(token):
            # If token is a number (integer or float)
            if re.fullmatch(r'\d+(?:\.\d+)?', token):
                # Use negative lookbehind and lookahead to ensure the token isn't part of a larger number.
                return r'(?<![\d.])' + re.escape(token) + r'(?![\d.])'
            else:
                # For alphabetic tokens, use word boundaries.
                return r'\b' + re.escape(token) + r'\b'
        # Build the overall pattern by joining each token pattern with '|'
        return '|'.join(boundary(token) for token in tokens)

    pattern = build_token_pattern(tokens_mapping.keys())
    
    def repl(match):
        token = match.group(0)
        return tokens_mapping.get(token, token)
    
    return re.sub(pattern, repl, string)


def replace_superscript_exponents(expr: str) -> str:
    """convert exponent to ** notation
    Example: "2a²b" becomes "2(a**2)b"
    """
    
    # Pattern for alphanumeric base followed by superscripts.
    pattern_base = r'([A-Za-z0-9π𝑒φ]+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
    
    def repl_base(match):
        base = match.group(1)
        superscripts = match.group(2)
        # Convert each superscript character to its digit equivalent.
        exponent = "".join(SUPERSCRIPTS.get(ch, '') for ch in superscripts)
        # Wrap the base in parentheses and apply the power operator.
        return f"({base}**{exponent})"
    
    # Pattern for a closing parenthesis immediately followed by superscripts.
    pattern_paren = r'(\))([⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
    
    def repl_paren(match):
        closing = match.group(1)
        superscripts = match.group(2)
        exponent = "".join(SUPERSCRIPTS.get(ch, '') for ch in superscripts)
        # Just insert ** before the exponent after the parenthesis.
        return f"){f'**{exponent}'}"
    
    expr = re.sub(pattern_base, repl_base, expr)
    expr = re.sub(pattern_paren, repl_paren, expr)
    return expr


def get_socket_python_api(node, identifier) -> str:
    """return a python api string that can be executed from a given node and socket identifier"""
    
    idx = None
    in_out_api = "inputs"
    for sockets in (node.inputs, node.outputs):
        for i,s in enumerate(sockets):
            if (hasattr(s,'identifier') and (s.identifier==identifier)):
                idx = i
                if (s.is_output):
                    in_out_api = "outputs"
                break
    
    assert idx is not None, 'ERROR: get_socket_python_api(): Did not find socket idx..'
    
    return f"ng.nodes['{node.name}'].{in_out_api}[{idx}]"


class NodeSetter():
    """Set the nodes depending on a given function expression"""
    
    @classmethod
    def get_functions(cls, get_names=False,):
        """get a list of all available functions"""

        r = set()
        
        for v in cls.__dict__.values():
            
            if (not isinstance(v, classmethod)):
                continue
            
            fname = v.__func__.__name__
            
            #ignore internal functions
            if fname.startswith('_'): 
                continue
            if fname in ('get_functions', 'execute_function_expression'):
                continue
            
            if (get_names):
                    r.add(fname)
            else: r.add(v.__func__)
                        
        return r
    
    @classmethod
    def execute_function_expression(cls, customnode=None, expression:str=None, node_tree=None, varsapi:dict=None, constapi:dict=None,) -> None | Exception:
        """Execute the functions to arrange the node_tree"""
        
        # Replace the constants or variable with sockets API
        api_expression = replace_exact_tokens(expression, {**varsapi, **constapi},)
        
        # Define the namespace of the execution, and include our functions
        namespace = {}
        namespace["ng"] = node_tree
        for f in cls.get_functions():
            namespace[f.__name__] = partial(f, cls)
        
        # Try to execute the functions:
        try:
            exec(api_expression, namespace)
            
        except TypeError as e:
            print(f"TypeError:\n  {e}\nOriginalExpression:\n  {expression}\nApiExpression:\n  {api_expression}\n")
            
            #Cook better error message to end user
            e = str(e)
            if e.startswith("NodeSetter."):
                fctname = str(e).split('NodeSetter.')[1].split('()')[0]

                if ('() missing' in e):
                    nbr = e.split('() missing ')[1][0]
                    return Exception(f"Function '{fctname}' needs {nbr} more Params")                    
                elif ('() takes' in e):
                    return Exception(f"Function '{fctname}' recieved Extra Params")
            
            return Exception("Wrong Arguments Given")
        
        except Exception as e:
            
            #Cook better error message to end user
            if ("'tuple' object" in str(e)):
                return Exception(f"Wrong use of '( , )' Synthax")
            
            print(f"ExecutionError:\n  {e}\nOriginalExpression:\n  {expression}\nApiExpression:\n  {api_expression}\n")
            return Exception("Error on Execution")
        
        # When executing, the last one created should be the active node, 
        # We still need to connect it to the ng output
        try:
            last = node_tree.nodes.active
            
            #this can only mean one thing, the user only inputed one single variable or constant
            if (last is None):
                if (customnode.elemVar):
                    last = node_tree.nodes['Group Input']
                elif (customnode.elemConst):
                    for n in node_tree.nodes:
                        if (n.type=='VALUE'):
                            last = n
                            break
                
            out_node = node_tree.nodes['Group Output']
            out_node.location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)
            
            sock1, sock2 = last.outputs[0], out_node.inputs[0]
            link_sockets(sock1, sock2)
            
        except Exception as e:
            print(f"FinalLinkError:\n  {e}")
            return Exception("Error on Final Link")
        
        return None            
    
    @classmethod
    def _floatmath(cls, operation_type, sock1, sock2=None, sock3=None,):
        """generic operation for adding a float math node and linking"""
        
        ng = sock1.id_data
        last = ng.nodes.active
        
        location = (0,200,)
        if (last):
            location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)

        node = ng.nodes.new('ShaderNodeMath')
        node.operation = operation_type
        node.use_clamp = False
        
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
                
        link_sockets(sock1, node.inputs[0])
        if (sock2):
            link_sockets(sock2, node.inputs[1])
        if (sock3):
            link_sockets(sock3, node.inputs[2])
            
        return node.outputs[0]
    
    @classmethod
    def _floatmath_nroot(cls, sock1, sock2):
        """special operation to calculate custom root x^(1/n)"""
        
        ng = sock1.id_data
        last = ng.nodes.active
        
        location = (0,200,)
        if (last):
            location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)

        divnode = ng.nodes.new('ShaderNodeMath')
        divnode.operation = 'DIVIDE'
        divnode.use_clamp = False
        
        divnode.location = location
        ng.nodes.active = divnode #Always set the last node active for the final link
                
        divnode.inputs[0].default_value = 1.0
        link_sockets(sock2, divnode.inputs[1])
        
        pnode = ng.nodes.new('ShaderNodeMath')
        pnode.operation = 'POWER'
        pnode.use_clamp = False
        
        last = divnode
        location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)
        
        pnode.location = location
        ng.nodes.active = pnode #Always set the last node active for the final link
                
        link_sockets(sock1, pnode.inputs[0])
        link_sockets(divnode.outputs[0], pnode.inputs[1])
            
        return pnode.outputs[0]
        
    @classmethod
    def _mix(cls, data_type, sock1, sock2, sock3,):
        """generic operation for adding a mix node and linking"""
        
        ng = sock1.id_data
        last = ng.nodes.active
        
        location = (0,200,)
        if (last):
            location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)

        node = ng.nodes.new('ShaderNodeMix')
        node.data_type = data_type
        node.clamp_factor = False
        
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        link_sockets(sock1, node.inputs[0])
        
        # Need to choose socket depending on node data_type (hidden sockets)
        match data_type:
            case 'FLOAT':
                link_sockets(sock2, node.inputs[2])
                link_sockets(sock3, node.inputs[3])
            case _:
                raise Exception("Integration Needed")
            
        return node.outputs[0]
    
    @classmethod
    def _floatclamp(cls, clamp_type, sock1, sock2, sock3,):
        """generic operation for adding a mix node and linking"""
        
        ng = sock1.id_data
        last = ng.nodes.active
        
        location = (0,200,)
        if (last):
            location = (last.location.x+last.width+NODE_X_OFFSET, last.location.y-NODE_Y_OFFSET,)

        node = ng.nodes.new('ShaderNodeClamp')
        node.clamp_type = clamp_type
        
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        link_sockets(sock1, node.inputs[0])
        link_sockets(sock2, node.inputs[1])
        link_sockets(sock3, node.inputs[2])
        
        return node.outputs[0]
    
    @classmethod
    def add(cls, sock1, sock2):
        return cls._floatmath('ADD', sock1, sock2)

    @classmethod
    def subtract(cls, sock1, sock2):
        return cls._floatmath('SUBTRACT', sock1, sock2)

    @classmethod
    def mult(cls, sock1, sock2):
        return cls._floatmath('MULTIPLY', sock1, sock2)

    @classmethod
    def div(cls, sock1, sock2):
        return cls._floatmath('DIVIDE', sock1, sock2)

    @classmethod
    def exp(cls, sock1, sock2):
        return cls._floatmath('POWER', sock1, sock2)

    @classmethod
    def power(cls, sock1, sock2): #Synonym of 'exp'
        return cls.exp(sock1, sock2)
    
    @classmethod
    def log(cls, sock1, sock2):
        return cls._floatmath('LOGARITHM', sock1, sock2)

    @classmethod
    def sqrt(cls, sock1):
        return cls._floatmath('SQRT', sock1)
    
    @classmethod
    def invsqrt(cls, sock1):
        return cls._floatmath('INVERSE_SQRT', sock1)
    
    @classmethod
    def nroot(cls, sock1, sock2):
        return cls._floatmath_nroot(sock1, sock2,)

    @classmethod
    def abs(cls, sock1):
        return cls._floatmath('ABSOLUTE', sock1)
    
    @classmethod
    def min(cls, sock1, sock2):
        return cls._floatmath('MINIMUM', sock1, sock2)
    
    @classmethod
    def max(cls, sock1, sock2):
        return cls._floatmath('MAXIMUM', sock1, sock2)
    
    @classmethod
    def round(cls, sock1):
        return cls._floatmath('ROUND', sock1)

    @classmethod
    def floor(cls, sock1):
        return cls._floatmath('FLOOR', sock1)

    @classmethod
    def ceil(cls, sock1):
        return cls._floatmath('CEIL', sock1)

    @classmethod
    def trunc(cls, sock1):
        return cls._floatmath('TRUNC', sock1)

    @classmethod
    def modulo(cls, sock1, sock2):
        return cls._floatmath('MODULO', sock1, sock2)
    
    @classmethod
    def wrap(cls, sock1, sock2, sock3):
        return cls._floatmath('WRAP', sock1, sock2, sock3)
    
    @classmethod
    def snap(cls, sock1, sock2):
        return cls._floatmath('SNAP', sock1, sock2)
    
    @classmethod
    def floordiv(cls, sock1, sock2): #Custom
        return cls.floor(cls.div(sock1,sock2),)
    
    @classmethod
    def sin(cls, sock1):
        return cls._floatmath('SINE', sock1)

    @classmethod
    def cos(cls, sock1):
        return cls._floatmath('COSINE', sock1)
    
    @classmethod
    def tan(cls, sock1):
        return cls._floatmath('TANGENT', sock1)

    @classmethod
    def asin(cls, sock1):
        return cls._floatmath('ARCSINE', sock1)

    @classmethod
    def acos(cls, sock1):
        return cls._floatmath('ARCCOSINE', sock1)
    
    @classmethod
    def atan(cls, sock1):
        return cls._floatmath('ARCTANGENT', sock1)
    
    @classmethod
    def hsin(cls, sock1):
        return cls._floatmath('SINH', sock1)

    @classmethod
    def hcos(cls, sock1):
        return cls._floatmath('COSH', sock1)
    
    @classmethod
    def htan(cls, sock1):
        return cls._floatmath('TANH', sock1)
    
    @classmethod
    def rad(cls, sock1):
        return cls._floatmath('RADIANS', sock1)
    
    @classmethod
    def deg(cls, sock1):
        return cls._floatmath('DEGREES', sock1)
    
    @classmethod
    def lerp(cls, sock1, sock2, sock3):
        return cls._mix('FLOAT', sock1, sock2, sock3)
    
    @classmethod
    def mix(cls, sock1, sock2, sock3): #Synonym of 'lerp'
        return cls.lerp(sock1, sock2, sock3)
    
    @classmethod
    def clamp(cls, sock1, sock2, sock3):
        return cls._floatclamp('MINMAX', sock1, sock2, sock3)
    
    @classmethod
    def clampr(cls, sock1, sock2, sock3):
        return cls._floatclamp('RANGE', sock1, sock2, sock3)


class FunctionTransformer(ast.NodeTransformer):
    """AST Transformer for converting math expressions into function-call expressions."""
    
    def __init__(self):
        super().__init__()
        self.functions_used = set()
    
    def visit_BinOp(self, node):
        # First, process child nodes.
        self.generic_visit(node)
        
        # Map ast operators and transform to supported function names
        match node.op:
            case ast.Add():
                func_name = 'add'
            case ast.Sub():
                func_name = 'subtract'
            case ast.Mult():
                func_name = 'mult'
            case ast.Div():
                func_name = 'div'
            case ast.Pow():
                func_name = 'exp'
            case ast.Mod():
                func_name = 'modulo'
            case ast.FloorDiv():
                func_name = 'floordiv'
            case _:
                raise NotImplementedError(f"Operator {node.op} not supported")
        
        self.functions_used.add(func_name)
        
        # Replace binary op with a function call.
        return ast.Call(
            func=ast.Name(id=func_name, ctx=ast.Load()),
            args=[node.left, node.right],
            keywords=[],
        )
    
    def visit_Call(self, node):
        # Record called function names.
        if isinstance(node.func, ast.Name):
            self.functions_used.add(node.func.id)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        return node

    def visit_Num(self, node):
        return node

    def visit_Constant(self, node):
        return node

    def transform_expression(self, math_express: str) -> str | Exception:
        """Transforms a math expression into a function-call expression.
        Example: 'x*2 + (3-4/5)/3 + (x+y)**2' becomes 'add(mult(x,2),div(subtract(3,div(4,5)),3),exp(add(x,y),2))'"""
        
        # Use the ast module to visit our equation
        try:
            tree = ast.parse(math_express, mode='eval')
            transformed_node = self.visit(tree.body)
        except Exception as e:
            print(e)
            return Exception("Math Expression Not Recognized")
        
        # Ensure all functions used are available valid
        funct_namespace = NodeSetter.get_functions(get_names=True)
        for fname in self.functions_used:
            if fname not in funct_namespace:
                return Exception(f"'{fname}' Function Not Recognized")
        
        # Then transform the ast into a function call sequence
        func_express = str(ast.unparse(transformed_node))
        return func_express


class EXTRANODES_NG_mathexpression(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodgroup: Evaluate a math expression using float math nodes.
    Under the hood, the expression will be sanarized, the transformed into functions that will be executed to create a new nodetree.
    The nodetree will be recomposed on each expression keystrokes"""
    
    #TODO later support multi type operation with blender with int/vector/bool operator?  and other math operation?
    #     - right now we only support the float math node.. we could support these other nodes
    #     - all vars could start with 'v' 'f' 'i' 'b' to designate their types?
    #     - could procedurally change sockets input/outputs depending on type
    #     - however, there will be a lot of checks required to see if the user is using valid types.. quite annoying. Perhaps could be done by checking 'is_valid'
    #     Or maybe create a separate 'ComplexMath' node and keep this simple one?
    
    #TODO what if user use a function with wrong number of arguments?
    #TODO support more math symbols? https://en.wikipedia.org/wiki/Glossary_of_mathematical_symbols
    #TODO color of the node header should be blue for converter.. how to do that without hacking in the memory??
    
    bl_idname = "GeometryNodeExtraMathExpression"
    bl_label = "Math Expression"

    error_message : bpy.props.StringProperty()
    debug_sanatized : bpy.props.StringProperty()
    debug_fctexp : bpy.props.StringProperty()
    
    def update_user_mathexp(self,context):
        """evaluate user expression and change the sockets implicitly"""
        self.apply_expression()
        return None 
    
    user_mathexp : bpy.props.StringProperty(
        default="a + b + c",
        name="Expression",
        update=update_user_mathexp,
        description="type your math expression right here",
    )
    implicit_mult : bpy.props.BoolProperty(
        default=False,
        name="Implicit Multiplication",
        update=update_user_mathexp,
        description="Automatically consider notation such as '2ab' as '2*a*b'",
    )
    auto_symbols : bpy.props.BoolProperty(
        default=False,
        name="Recognize Irrationals",
        update=update_user_mathexp,
        description="Automatically recognize the irrational constants 'π' '𝑒' 'φ' from the macros 'Pi' 'eNum' 'Gold'.\nThe constant will be set in float, up to 7 decimals",
    )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context,):        
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"
        
        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                out_sockets={
                    "Result" : "NodeSocketFloat",
                },
            )
         
        ng = ng.copy() #always using a copy of the original ng

        self.node_tree = ng
        self.width = 250
        self.label = self.bl_label

        #initialize default expression
        self.user_mathexp = self.user_mathexp

        return None 

    def copy(self,node,):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None 
    
    def update(self):
        """generic update function"""
                
        return None
    
    def sanatize_expression(self, expression) -> str | Exception:
        """ensure the user expression is correct, sanatized it, and collect its element"""
        
        synthax, operand = '.,()', '/*-+%'
        funct_namespace = NodeSetter.get_functions(get_names=True)

        # First we format some symbols
        expression = expression.replace(' ','')
                
        # Sanatize ² Notations
        for char in expression:
            if char in SUPERSCRIPTS.keys():
                #NOTE once 'self.implicit_mult' is implemented, parentheses behavior will need to change
                expression = replace_superscript_exponents(expression)
                break 
        
        # Support for Irrational numbers (Pi ect.., we need to replace their tokens)
        mached = match_exact_tokens(expression, [v['unicode'] for v in IRRATIONALS.values()])
        if any(mached):
            expression = replace_exact_tokens(
                expression,
                {v['unicode']:v['value'] for v in IRRATIONALS.values() if (v['unicode'] in mached)}
            )
        
        # Make a list of authorized symbols
        authorized_symbols = ''
        authorized_symbols += synthax
        authorized_symbols += operand
        authorized_symbols += ''.join(chr(c) for c in range(ord('a'), ord('z') + 1)) #alphabet
        authorized_symbols += ''.join(chr(c).upper() for c in range(ord('a'), ord('z') + 1)) #alphabet upper
        authorized_symbols += ''.join(chr(c) for c in range(ord('0'), ord('9') + 1)) #numbers
        
        # Gather lists of expression component outside of operand and some synthax elements
        elemTotal = expression
        for char in operand + ',()':
            elemTotal = elemTotal.replace(char,'|')
        self.elemTotal = set(e for e in elemTotal.split('|') if e!='')
        
        # Sort elements, they can be either variables, constants, functions, or unrecognized
        self.elemFct = set()
        self.elemConst = set()
        self.elemVar = set()
        self.elemCmplx = set()
        
        match self.implicit_mult:
            
            case True:
                for e in self.elemTotal:
                    
                    #we have a function
                    if (e in funct_namespace):
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue
                    
                    #we have float or int
                    if (e.replace('.','').isdigit()):
                        self.elemConst.add(e)
                        continue
                    
                    #we have a variable (ex 'ab' or 'x')
                    if e.isalpha():
                        self.elemVar.add(e)
                        continue
                    
                    #We have a composite (ex 2ab)
                    if any(c.isdigit() for c in e):
                        self.elemCmplx.add(e) #We have a composite (ex 2ab²)
                        continue
                    
                    #We have an urecognized element
                    return Exception(f"Unrecorgnized Variable '{e}'")
                
            case False:
                for e in self.elemTotal:
                    
                    #we have a function
                    if (e in funct_namespace):
                        self.elemFct.add(e)
                        continue
                    
                    #we have float or int
                    if (e.replace('.','').isdigit()):
                        # if (f'{e}(' in expression):
                        #     return Exception(f"'{e}(' Expression Not Supported")
                        self.elemConst.add(e)
                        continue
                    
                    #we have a variable (ex 'ab' or 'x')
                    if e.isalpha():
                        if (e in funct_namespace):
                            return Exception(f"Variable '{e}' is Taken")
                        self.elemVar.add(e)
                        continue
                    
                    #We have an urecognized element
                    return Exception(f"Unrecorgnized Variable '{e}'")
        
        # Ensure user is using correct symbols
        for char in expression:
            if (char not in authorized_symbols):
                return Exception(f"Unrecorgnized Symbol '{char}'")
        
        # Support for implicit math operation on parentheses (ex 2(a+b) or 2.59(c²))
        expression = re.sub(r"(\d+(?:\.\d+)?)(\()", r"\1*\2", expression)
        
        return expression
    
    def apply_expression(self) -> None:
        """transform the math expression into sockets and nodes arrangements"""
        
        ng = self.node_tree 
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]
        
        # Reset error message
        self.error_message = self.debug_sanatized = self.debug_fctexp = ""
        
        # Support for automatically replacing some symbols
        if (self.auto_symbols):
            mached = match_exact_tokens(self.user_mathexp, IRRATIONALS.keys())
            if any(mached):
                self.user_mathexp = replace_exact_tokens(
                    self.user_mathexp,
                    {k:v['unicode'] for k,v in IRRATIONALS.items() if (k in mached)}
                )
                #We just sent an update signal to "user_mathexp", the function will restart shortly..
                return None
            
        # First we make sure the user expression is correct
        rval = self.sanatize_expression(self.user_mathexp)
        if (type(rval) is Exception):
            self.error_message = str(rval)
            self.debug_sanatized = 'Failed'
            return None
        
        # Define the result of sanatize_expression
        sanatized_expr = self.debug_sanatized = rval
        elemVar, elemConst = self.elemVar, self.elemConst
        
        # Clear node tree
        for node in list(ng.nodes):
            if node.type not in {'GROUP_INPUT', 'GROUP_OUTPUT'}:
                ng.nodes.remove(node)
                
        # Create new sockets depending on vars
        if (elemVar):
            current_vars = [s.name for s in in_nod.outputs]
            for var in elemVar:
                if (var not in current_vars):
                    create_socket(ng, in_out='INPUT', socket_type="NodeSocketFloat", socket_name=var,)
        
        # Remove unused vars sockets
        idx_to_del = []
        for idx,socket in enumerate(in_nod.outputs):
            if ((socket.type!='CUSTOM') and (socket.name not in elemVar)):
                idx_to_del.append(idx)
        for idx in reversed(idx_to_del):
            remove_socket(ng, idx, in_out='INPUT')
        
        # Let's collect equivalence between varnames/const and the pythonAPI
        vareq, consteq = dict(), dict()
        
        # Fill equivalence dict with it's socket eq
        if (elemVar):
            for s in in_nod.outputs:
                if (s.name in elemVar):
                    vareq[s.name] = get_socket_python_api(in_nod, s.identifier)
                
        # Add input for constant right below the vars group input
        if (elemConst):
            xloc, yloc = in_nod.location.x, in_nod.location.y-330
            for const in elemConst:
                con_nod = ng.nodes.new('ShaderNodeValue')
                con_nod.outputs[0].default_value = float(const)
                con_nod.name = const
                con_nod.label = const
                con_nod.location.x = xloc
                con_nod.location.y = yloc
                yloc -= 90
                # Also fill const to socket equivalence dict
                consteq[const] = get_socket_python_api(con_nod, con_nod.outputs[0].identifier)
        
        # Give it a refresh signal, when we remove/create a lot of sockets, the customnode inputs/outputs needs a kick
        self.update_all()
        
        # if we don't have any elements to work with, quit
        if not (elemVar or elemConst):
            return None
        
        # Transform user expression into pure function expression
        transformer = FunctionTransformer()
        fctexp = transformer.transform_expression(sanatized_expr)

        if (type(fctexp) is Exception):
            self.error_message = str(fctexp)
            self.debug_fctexp = 'Failed'
            return None
        
        self.debug_fctexp = fctexp
        
        # Execute the function expression to arrange the user nodetree
        rval = NodeSetter.execute_function_expression(
            customnode=self, expression=fctexp, node_tree=ng, varsapi=vareq, constapi=consteq,
            )
        
        if (type(rval) is Exception):
            self.error_message = str(rval)
            return None
        
        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self, context, layout,):
        """node interface drawing"""
                
        col = layout.column(align=True)
        
        row = col.row(align=True)
        row.alert = bool(self.error_message)
        row.prop(self,"user_mathexp", text="",)
        
        # opt = row.row(align=True)
        # opt.scale_x = 0.35
        # opt.prop(self, "implicit_mult", text="ab", toggle=True, )
        
        opt = row.row(align=True)
        opt.scale_x = 0.3
        opt.prop(self, "auto_symbols", text="π", toggle=True, )
        
        if (self.error_message):
            lbl = col.row()
            lbl.alert = bool(self.error_message)
            lbl.label(text=self.error_message)
        
        layout.separator(factor=0.75)
        
        return None

    def draw_buttons_ext(self, context, layout):
        """draw in the N panel when the node is selected"""
        
        col = layout.column(align=True)
        col.label(text="Expression:")
        row = col.row(align=True)
        row.alert = bool(self.error_message)
        row.prop(self,"user_mathexp", text="",)
        
        layout.prop(self, "auto_symbols",)
        
        if (self.error_message):
            lbl = col.row()
            lbl.alert = bool(self.error_message)
            lbl.label(text=self.error_message)
        
        layout.separator(factor=1.2,type='LINE')
        
        col = layout.column(align=True)
        col.label(text="SanatizedExp:")
        row = col.row()
        row.enabled = False
        row.prop(self, "debug_sanatized", text="",)

        layout.separator(factor=1.2,type='LINE')
        
        col = layout.column(align=True)
        col.label(text="FunctionExp:")
        row = col.row()
        row.enabled = False
        row.prop(self, "debug_fctexp", text="",)
        
        layout.separator(factor=1.2,type='LINE')
        
        col = layout.column(align=True)
        col.label(text="Operators:")
        op = col.operator("extranode.bake_mathexpression", text="Convert to Group",)
        op.nodegroup_name = self.node_tree.name
        op.node_name = self.name
        
        layout.separator(factor=1.2,type='LINE')
            
        col = layout.column(align=True)
        col.label(text="NodeTree:")
        col.template_ID(self, "node_tree")
        
        layout.separator(factor=1.2,type='LINE')
        
        col = layout.column(align=True)
        col.label(text="Variables:")
        #... groups inputs will be drawn below
        
        return None
    
    @classmethod
    def update_all(cls):
        """search for all nodes of this type and update them"""
        
        for n in [n for ng in bpy.data.node_groups for n in ng.nodes if (n.bl_idname==cls.bl_idname)]:
            n.update()
            
        return None


class EXTRANODES_OT_bake_mathexpression(bpy.types.Operator):
    """Replace the custom node with a nodegroup, preserve values and links"""
    
    bl_idname = "extranode.bake_mathexpression"
    bl_label = "Bake Expression"
    bl_options = {'REGISTER', 'UNDO'}

    nodegroup_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        
        space = context.space_data
        if not space or not hasattr(space, "edit_tree") or space.edit_tree is None:
            self.report({'ERROR'}, "No active node tree found")
            return {'CANCELLED'}
        node_tree = space.edit_tree

        old_node = node_tree.nodes.get(self.node_name)
        if (old_node is None):
            self.report({'ERROR'}, "Node with given name not found")
            return {'CANCELLED'}

        node_group = bpy.data.node_groups.get(self.nodegroup_name)
        if (node_group is None):
            self.report({'ERROR'}, "Node group with given name not found")
            return {'CANCELLED'}

        old_exp = str(old_node.user_mathexp)
        node_group = node_group.copy()
        node_group.name = f'{node_group.name}.Baked'
        
        new_node = replace_node(node_tree, old_node, node_group,)
        new_node.label = old_exp
        
        self.report({'INFO'}, f"Replaced node '{self.node_name}' with node group '{self.node_name}'")
        
        return {'FINISHED'}
