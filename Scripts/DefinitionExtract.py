#!/usr/bin/python3
import clang.cindex
from clang.cindex import CursorKind
from clang.cindex import TypeKind
from clang.cindex import TranslationUnit
import sys
from dataclasses import dataclass, field
import subprocess
import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)

@dataclass
class TypeDefinition:
    TYPE_UNKNOWN = 0
    TYPE_STRUCT = 1
    TYPE_UNION = 2
    TYPE_FIELD = 3
    TYPE_VARDECL = 4

    name: str
    type: int
    def __init__(self, Name, Type):
        self.name = Name
        self.type = Type

    @property
    def Name(self):
        return self.name
    @property
    def Type(self):
        return self.type

@dataclass
class AliasType:
    ALIAS_X86_32  = 0
    ALIAS_X86_64  = 1
    ALIAS_AARCH64 = 2
    ALIAS_WIN32   = 3
    ALIAS_WIN64   = 4
    Name: str
    AliasType: int
    def __init__(self, Name, Type):
        self.Name = Name
        self.AliasType = Type

@dataclass
class StructDefinition(TypeDefinition):
    Size: int
    Aliases: list
    Members: list
    ExpectFEXMatch: bool

    def __init__(self, Name, Size):
        super(StructDefinition, self).__init__(Name, TypeDefinition.TYPE_STRUCT)
        self.Size = Size
        self.Aliases = []
        self.Members = []
        self.ExpectFEXMatch = False

@dataclass
class UnionDefinition(TypeDefinition):
    Size: int
    Aliases: list
    Members: list
    ExpectFEXMatch: bool

    def __init__(self, Name, Size):
        super(UnionDefinition, self).__init__(Name, TypeDefinition.TYPE_UNION)
        self.Size = Size
        self.Aliases = []
        self.Members = []
        self.ExpectFEXMatch = False

@dataclass
class FieldDefinition(TypeDefinition):
    Size: int
    OffsetOf: int
    Alignment: int
    def __init__(self, Name, Size, OffsetOf, Alignment):
        super(FieldDefinition, self).__init__(Name, TypeDefinition.TYPE_FIELD)
        self.Size = Size
        self.OffsetOf = OffsetOf
        self.Alignment = Alignment

@dataclass
class VarDeclDefinition(TypeDefinition):
    Size: int
    Aliases: list
    ExpectFEXMatch: bool
    Value: str

    def __init__(self, Name, Size):
        super(VarDeclDefinition, self).__init__(Name, TypeDefinition.TYPE_VARDECL)
        self.Size = Size
        self.Aliases = []
        self.ExpectFEXMatch = False

@dataclass
class ArchDB:
    Parsed: bool
    ArchName: str
    NamespaceScope: list
    CurrentNamespace: str
    TU: TranslationUnit
    Structs: dict
    Unions: dict
    VarDecls: dict
    FieldDecls: list
    def __init__(self, ArchName):
        self.Parsed = True
        self.ArchName = ArchName
        self.NamespaceScope = []
        self.CurrentNamespace = ""
        self.TU = None
        self.Structs = {}
        self.Unions = {}
        self.VarDecls = {}
        self.FieldDecls = []

@dataclass
class FunctionDecl:
    Name: str
    Ret: str
    Params: list

    def __init__(self, Name, Ret):
        self.Name = Name
        self.Ret = Ret
        self.Params = []

FunctionDecls = []

def HandleFunctionDeclCursor(Arch, Cursor):
    if (Cursor.is_definition()):
        return Arch

    #logging.critical ("Unhandled FunctionDeclCursor {0}-{1}-{2}-{3}".format(Cursor.kind, Cursor.type.spelling, Cursor.spelling,
    #    Cursor.result_type.spelling))

    Function = FunctionDecl(Cursor.spelling, Cursor.result_type.spelling)

    for Child in Cursor.get_children():
        if (Child.kind == CursorKind.TYPE_REF):
            continue
        if (Child.kind == CursorKind.PARM_DECL):
            # This gives us a parameter type
            Function.Params.append(Child.type.spelling)
        elif (Child.kind == CursorKind.ASM_LABEL_ATTR):
            # Whatever you are we don't care about you
            return Arch
        elif (Child.kind == CursorKind.WARN_UNUSED_RESULT_ATTR):
            # Whatever you are we don't care about you
            return Arch
        elif Child.kind not in [
            CursorKind.VISIBILITY_ATTR,
            CursorKind.UNEXPOSED_ATTR,
            CursorKind.CONST_ATTR,
            CursorKind.PURE_ATTR,
        ]:
            logging.critical ("\tUnhandled FunctionDeclCursor {0}-{1}-{2}".format(Child.kind, Child.type.spelling, Child.spelling))
            sys.exit(-1)

    FunctionDecls.append(Function)
    return Arch

def PrintFunctionDecls():
    for Decl in FunctionDecls:
        print("template<> struct fex_gen_config<{}> {{}};".format(Decl.Name))

def FindClangArguments(OriginalArguments):
    AddedArguments = ["clang"]
    AddedArguments.extend(OriginalArguments)
    AddedArguments.extend(["-v", "-x", "c++", "-S", "-"])
    Proc = subprocess.Popen(AddedArguments, stderr = subprocess.PIPE, stdin = subprocess.DEVNULL)
    NewIncludes = []
    BeginSearch = False
    while True:
        Line = Proc.stderr.readline().strip()

        if not Line:
            Proc.terminate()
            break

        if (Line == b"End of search list."):
            BeginSearch = False
            Proc.terminate()
            break

        if (BeginSearch == True):
            NewIncludes.append("-I" + Line.decode('ascii'))

        if (Line == b"#include <...> search starts here:"):
            BeginSearch = True

    # Add back original arguments
    NewIncludes.extend(OriginalArguments)
    return NewIncludes

def SetNamespace(Arch):
    Arch.CurrentNamespace = ""
    for Namespace in Arch.NamespaceScope:
        Arch.CurrentNamespace = Arch.CurrentNamespace + Namespace + "::"

def HandleStructDeclCursor(Arch, Cursor, NameOverride = ""):
    # Append namespace
    CursorName = ""
    StructType = Cursor.type
    if (len(StructType.spelling) == 0):
        CursorName = NameOverride
    else:
        CursorName = StructType.spelling

    if (len(CursorName) != 0):
        Arch.NamespaceScope.append(CursorName)
        SetNamespace(Arch)

    Struct = StructDefinition(
        Name = CursorName,
        Size = StructType.get_size())

    # Handle children
    Arch.Structs[Struct.Name] = HandleStructElements(Arch, Struct, Cursor)

    # Pop namespace off
    if (len(CursorName) != 0):
        Arch.NamespaceScope.pop()
        SetNamespace(Arch)

    return Arch

def HandleUnionDeclCursor(Arch, Cursor, NameOverride = ""):
    # Append namespace
    CursorName = ""

    CursorName = NameOverride if (len(Cursor.spelling) == 0) else Cursor.spelling
    if (len(CursorName) != 0):
        Arch.NamespaceScope.append(CursorName)
        SetNamespace(Arch)

    UnionType = Cursor.type
    Union = UnionDefinition(
        Name = CursorName,
        Size = UnionType.get_size())
    Arch.Unions[Union.Name] = Union

    # Handle children
    Arch.Unions[Union.Name] = HandleStructElements(Arch, Union, Cursor)

    # Pop namespace off
    if (len(CursorName) != 0):
        Arch.NamespaceScope.pop()
        SetNamespace(Arch)

    return Arch

def HandleVarDeclCursor(Arch, Cursor):
    CursorName = Cursor.spelling
    DeclType = Cursor.type
    Def = Cursor.get_definition()

    VarDecl = VarDeclDefinition(
        Name = CursorName,
        Size = DeclType.get_size())
    Arch.VarDecls[VarDecl.Name] = HandleVarDeclElements(Arch, VarDecl, Cursor)
    return Arch

def HandleVarDeclElements(Arch, VarDecl, Cursor):
    for Child in Cursor.get_children():

        if (Child.kind == CursorKind.ANNOTATE_ATTR):
            if (Child.spelling.startswith("ioctl-alias-")):
                Sections = Child.spelling.split("-")
                if (Sections[2] == "x86_32"):
                    VarDecl.Aliases.append(AliasType(Sections[3], AliasType.ALIAS_X86_32))
                elif (Sections[2] == "x86_64"):
                    VarDecl.Aliases.append(AliasType(Sections[3], AliasType.ALIAS_X86_64))
                elif (Sections[2] == "aarch64"):
                    VarDecl.Aliases.append(AliasType(Sections[3], AliasType.ALIAS_AARCH64))
                elif (Sections[2] == "win32"):
                    VarDecl.Aliases.append(AliasType(Sections[3], AliasType.ALIAS_WIN32))
                elif (Sections[2] == "win64"):
                    VarDecl.Aliases.append(AliasType(Sections[3], AliasType.ALIAS_WIN64))
                else:
                    logging.critical ("Can't handle alias type '{0}'".format(Child.spelling))
                    Arch.Parsed = False
            elif (Child.spelling == "fex-match"):
                VarDecl.ExpectedFEXMatch = True
    return VarDecl

def HandleTypeDefDeclCursor(Arch, Cursor):
    TypeDefType = Cursor.underlying_typedef_type
    CanonicalType = TypeDefType.get_canonical()

    TypeDefName = Cursor.type.get_typedef_name()

    if (len(TypeDefName) != 0):
        if (TypeDefType.kind == TypeKind.ELABORATED and CanonicalType.kind == TypeKind.RECORD):
            HandleTypeDefDecl(Arch, Cursor, TypeDefName)

	    # Append namespace
            Arch.NamespaceScope.append(TypeDefName)
            SetNamespace(Arch)

            Arch = HandleCursor(Arch, Cursor)
            #StructType = Cursor.type
            #Struct = StructDefinition(
            #    Name = TypeDefName,
            #    Size = CanonicalType.get_size())
            #Arch.Structs[TypeDefName] = Struct

            ## Handle children
            #Arch.Structs[TypeDefName] = HandleStructElements(Arch, Struct, Cursor)

            # Pop namespace off
            Arch.NamespaceScope.pop()
            SetNamespace(Arch)
        else:
            Def = Cursor.get_definition()

            VarDecl = VarDeclDefinition(
                Name = TypeDefName,
                Size = CanonicalType.get_size())
            Arch.VarDecls[VarDecl.Name] = HandleVarDeclElements(Arch, VarDecl, Cursor)

    return Arch

def HandleStructElements(Arch, Struct, Cursor):
    for Child in Cursor.get_children():
        # logging.info ("\t\tStruct/Union Children: Cursor \"{0}{1}\" of kind {2}".format(Arch.CurrentNamespace, Child.spelling, Child.kind))
        if (Child.kind == CursorKind.ANNOTATE_ATTR):
            if (Child.spelling.startswith("alias-")):
                Sections = Child.spelling.split("-")
                if (Sections[1] == "x86_32"):
                    Struct.Aliases.append(AliasType(Sections[2], AliasType.ALIAS_X86_32))
                elif (Sections[1] == "x86_64"):
                    Struct.Aliases.append(AliasType(Sections[2], AliasType.ALIAS_X86_64))
                elif (Sections[1] == "aarch64"):
                    Struct.Aliases.append(AliasType(Sections[2], AliasType.ALIAS_AARCH64))
                elif (Sections[1] == "win32"):
                    Struct.Aliases.append(AliasType(Sections[2], AliasType.ALIAS_WIN32))
                elif (Sections[1] == "win64"):
                    Struct.Aliases.append(AliasType(Sections[2], AliasType.ALIAS_WIN64))
                else:
                    logging.critical ("Can't handle alias type '{0}'".format(Child.spelling))
                    Arch.Parsed = False

            elif (Child.spelling == "fex-match"):
                Struct.ExpectedFEXMatch = True
        elif (Child.kind == CursorKind.FIELD_DECL):
            ParentType = Cursor.type
            FieldType = Child.type
            Field = FieldDefinition(
                Name = Child.spelling,
                Size = FieldType.get_size(),
                OffsetOf = ParentType.get_offset(Child.spelling),
                Alignment = FieldType.get_align())

            #logging.info ("\t{0}".format(Child.spelling))
            #logging.info ("\t\tSize of type: {0}".format(FieldType.get_size()));
            #logging.info ("\t\tAlignment of type: {0}".format(FieldType.get_align()));
            #logging.info ("\t\tOffsetof of type: {0}".format(ParentType.get_offset(Child.spelling)));
            Struct.Members.append(Field)
            Arch.FieldDecls.append(Field)
        elif (Child.kind == CursorKind.STRUCT_DECL):
            ParentType = Cursor.type
            FieldType = Child.type
            Field = FieldDefinition(
                Name = Child.spelling,
                Size = FieldType.get_size(),
                OffsetOf = ParentType.get_offset(Child.spelling),
                Alignment = FieldType.get_align())

            #logging.info ("\t{0}".format(Child.spelling))
            #logging.info ("\t\tSize of type: {0}".format(FieldType.get_size()));
            #logging.info ("\t\tAlignment of type: {0}".format(FieldType.get_align()));
            #logging.info ("\t\tOffsetof of type: {0}".format(ParentType.get_offset(Child.spelling)));
            Struct.Members.append(Field)
            Arch.FieldDecls.append(Field)
            Arch = HandleStructDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.UNION_DECL):
            Struct = HandleStructElements(Arch, Struct, Child)
            #ParentType = Cursor.type
            #FieldType = Child.type
            #Field = FieldDefinition(
            #    Name = Child.spelling,
            #    Size = FieldType.get_size(),
            #    OffsetOf = ParentType.get_offset(Child.spelling),
            #    Alignment = FieldType.get_align())

            #logging.info ("\t{0}".format(Child.spelling))
            #logging.info ("\t\tSize of type: {0}".format(FieldType.get_size()));
            #logging.info ("\t\tAlignment of type: {0}".format(FieldType.get_align()));
            #logging.info ("\t\tOffsetof of type: {0}".format(ParentType.get_offset(Child.spelling)));
            #Struct.Members.append(Field)
            #Arch.FieldDecls.append(Field)
            #Arch = HandleUnionDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.TYPEDEF_DECL):
            Arch = HandleTypeDefDeclCursor(Arch, Child)
        else:
            Arch = HandleCursor(Arch, Child)

    return Struct

def HandleTypeDefDecl(Arch, Cursor, Name):
    for Child in Cursor.get_children():
        if (Child.kind == CursorKind.UNION_DECL):
            continue
        if (Child.kind == CursorKind.STRUCT_DECL):
            Arch = HandleStructDeclCursor(Arch, Child, Name)
        elif (Child.kind == CursorKind.TYPEDEF_DECL):
            Arch = HandleTypeDefDeclCursor(Arch, Child)
        elif Child.kind not in [
            CursorKind.TYPE_REF,
            CursorKind.NAMESPACE_REF,
            CursorKind.TEMPLATE_REF,
            CursorKind.ALIGNED_ATTR,
        ]:
            logging.critical ("Unhandled TypedefDecl {0}-{1}-{2}".format(Child.kind, Child.type.spelling, Child.spelling))

def HandleCursor(Arch, Cursor):
    if (Cursor.kind.is_invalid()):
        Diags = TU.diagnostics
        for Diag in Diags:
            logging.warning (Diag.format())

        Arch.Parsed = False
        return

    for Child in Cursor.get_children():
        if (Child.kind == CursorKind.TRANSLATION_UNIT):
            Arch = HandleCursor(Arch, Child)
        elif (Child.kind == CursorKind.FIELD_DECL):
            pass
        elif (Child.kind == CursorKind.UNION_DECL):
            Arch = HandleUnionDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.STRUCT_DECL):
            Arch = HandleStructDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.TYPEDEF_DECL):
            Arch = HandleTypeDefDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.VAR_DECL):
            Arch = HandleVarDeclCursor(Arch, Child)
        elif (Child.kind == CursorKind.NAMESPACE):
            # Append namespace
            Arch.NamespaceScope.append(Child.spelling)
            SetNamespace(Arch)

            # Handle children
            Arch = HandleCursor(Arch, Child)

            # Pop namespace off
            Arch.NamespaceScope.pop()
            SetNamespace(Arch)
        elif (Child.kind == CursorKind.TYPE_REF):
            # Safe to pass on
            pass
        elif (Child.kind == CursorKind.FUNCTION_DECL):
            # For function printing
            Arch = HandleFunctionDeclCursor(Arch, Child)
        else:
            Arch = HandleCursor(Arch, Child)

    return Arch

def GetDB(Arch, filename, args):
    Index = clang.cindex.Index.create()
    try:
        TU = Index.parse(filename, args=args, options=TranslationUnit.PARSE_INCOMPLETE)
    except TranslationUnitLoadError:
        Arch.Parsed = False
        Diags = TU.diagnostics
        for Diag in Diags:
            logging.warning (Diag.format())

        return

    Arch.TU = TU
    FunctionDecls.clear()
    HandleCursor(Arch, TU.cursor)

    # Get diagnostics
    Diags = TU.diagnostics
    if (len(Diags) != 0):
        logging.warning ("Diagnostics from Arch: {0}".format(Arch.ArchName))

    for Diag in Diags:
        logging.warning (Diag.format())

    return Arch

def main():
    if sys.version_info[0] < 3:
        logging.critical ("Python 3 or a more recent version is required.")

    if (len(sys.argv) < 2):
        print(f"usage: {sys.argv[0]} <Header.hpp> <clang arguments...>")

    Header = ""
    # Parse our arguments
    Header = sys.argv[1]

    BaseArgs = [sys.argv[ArgIndex] for ArgIndex in range(2, len(sys.argv))]
    args_x86_64 = [
        "-I/usr/include/x86_64-linux-gnu",
        "-I/usr/x86_64-linux-gnu/include/c++/10/x86_64-linux-gnu/",
        "-I/usr/x86_64-linux-gnu/include/",
        "-O2",
        "--target=x86_64-linux-unknown",
        "-D_M_X86_64",
        *BaseArgs,
    ]

    # We need to find the default arguments through clang invocations
    args_x86_64 = FindClangArguments(args_x86_64)

    Arch_x86_64 = ArchDB("x86_64")
    Arch_x86_64 = GetDB(Arch_x86_64, Header, args_x86_64)
    PrintFunctionDecls()

if __name__ == "__main__":
# execute only if run as a script
    sys.exit(main())
