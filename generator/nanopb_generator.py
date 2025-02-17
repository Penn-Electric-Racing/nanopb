#!/usr/bin/env python
# kate: replace-tabs on; indent-width 4;

from __future__ import unicode_literals

'''Generate header file for nanopb from a ProtoBuf FileDescriptorSet.'''
nanopb_version = "nanopb-0.4.0-dev"

import sys
import re
import codecs
import copy
from functools import reduce

try:
    # Add some dummy imports to keep packaging tools happy.
    import google, distutils.util # bbfreeze seems to need these
    import pkg_resources # pyinstaller / protobuf 2.5 seem to need these
except:
    # Don't care, we will error out later if it is actually important.
    pass

try:
    import google.protobuf.text_format as text_format
    import google.protobuf.descriptor_pb2 as descriptor
    import google.protobuf.compiler.plugin_pb2 as plugin_pb2
    import google.protobuf.reflection as reflection
    import google.protobuf.descriptor
except:
    sys.stderr.write('''
         *************************************************************
         *** Could not import the Google protobuf Python libraries ***
         *** Try installing package 'python-protobuf' or similar.  ***
         *************************************************************
    ''' + '\n')
    raise

try:
    import proto.nanopb_pb2 as nanopb_pb2
except TypeError:
    sys.stderr.write('''
         ****************************************************************************
         *** Got TypeError when importing the protocol definitions for generator. ***
         *** This usually means that the protoc in your path doesn't match the    ***
         *** Python protobuf library version.                                     ***
         ***                                                                      ***
         *** Please check the output of the following commands:                   ***
         *** which protoc                                                         ***
         *** protoc --version                                                     ***
         *** python -c 'import google.protobuf; print(google.protobuf.__file__)'  ***
         *** If you are not able to find the python protobuf version using the    ***
         *** above command, use this command.                                     ***
         *** pip freeze | grep -i protobuf                                        ***
         ****************************************************************************
    ''' + '\n')
    raise
except:
    sys.stderr.write('''
         ********************************************************************
         *** Failed to import the protocol definitions for generator.     ***
         *** You have to run 'make' in the nanopb/generator/proto folder. ***
         ********************************************************************
    ''' + '\n')
    raise

# ---------------------------------------------------------------------------
#                     Generation of single fields
# ---------------------------------------------------------------------------

import time
import os.path

# Values are tuple (c type, pb type, encoded size, data_size)
FieldD = descriptor.FieldDescriptorProto
datatypes = {
    FieldD.TYPE_BOOL:       ('bool',     'BOOL',        1,  4),
    FieldD.TYPE_DOUBLE:     ('double',   'DOUBLE',      8,  8),
    FieldD.TYPE_FIXED32:    ('uint32_t', 'FIXED32',     4,  4),
    FieldD.TYPE_FIXED64:    ('uint64_t', 'FIXED64',     8,  8),
    FieldD.TYPE_FLOAT:      ('float',    'FLOAT',       4,  4),
    FieldD.TYPE_INT32:      ('int32_t',  'INT32',      10,  4),
    FieldD.TYPE_INT64:      ('int64_t',  'INT64',      10,  8),
    FieldD.TYPE_SFIXED32:   ('int32_t',  'SFIXED32',    4,  4),
    FieldD.TYPE_SFIXED64:   ('int64_t',  'SFIXED64',    8,  8),
    FieldD.TYPE_SINT32:     ('int32_t',  'SINT32',      5,  4),
    FieldD.TYPE_SINT64:     ('int64_t',  'SINT64',     10,  8),
    FieldD.TYPE_UINT32:     ('uint32_t', 'UINT32',      5,  4),
    FieldD.TYPE_UINT64:     ('uint64_t', 'UINT64',     10,  8),

    # Integer size override options
    (FieldD.TYPE_INT32,   nanopb_pb2.IS_8):   ('int8_t',   'INT32', 10,  1),
    (FieldD.TYPE_INT32,  nanopb_pb2.IS_16):   ('int16_t',  'INT32', 10,  2),
    (FieldD.TYPE_INT32,  nanopb_pb2.IS_32):   ('int32_t',  'INT32', 10,  4),
    (FieldD.TYPE_INT32,  nanopb_pb2.IS_64):   ('int64_t',  'INT32', 10,  8),
    (FieldD.TYPE_SINT32,  nanopb_pb2.IS_8):   ('int8_t',  'SINT32',  2,  1),
    (FieldD.TYPE_SINT32, nanopb_pb2.IS_16):   ('int16_t', 'SINT32',  3,  2),
    (FieldD.TYPE_SINT32, nanopb_pb2.IS_32):   ('int32_t', 'SINT32',  5,  4),
    (FieldD.TYPE_SINT32, nanopb_pb2.IS_64):   ('int64_t', 'SINT32', 10,  8),
    (FieldD.TYPE_UINT32,  nanopb_pb2.IS_8):   ('uint8_t', 'UINT32',  2,  1),
    (FieldD.TYPE_UINT32, nanopb_pb2.IS_16):   ('uint16_t','UINT32',  3,  2),
    (FieldD.TYPE_UINT32, nanopb_pb2.IS_32):   ('uint32_t','UINT32',  5,  4),
    (FieldD.TYPE_UINT32, nanopb_pb2.IS_64):   ('uint64_t','UINT32', 10,  8),
    (FieldD.TYPE_INT64,   nanopb_pb2.IS_8):   ('int8_t',   'INT64', 10,  1),
    (FieldD.TYPE_INT64,  nanopb_pb2.IS_16):   ('int16_t',  'INT64', 10,  2),
    (FieldD.TYPE_INT64,  nanopb_pb2.IS_32):   ('int32_t',  'INT64', 10,  4),
    (FieldD.TYPE_INT64,  nanopb_pb2.IS_64):   ('int64_t',  'INT64', 10,  8),
    (FieldD.TYPE_SINT64,  nanopb_pb2.IS_8):   ('int8_t',  'SINT64',  2,  1),
    (FieldD.TYPE_SINT64, nanopb_pb2.IS_16):   ('int16_t', 'SINT64',  3,  2),
    (FieldD.TYPE_SINT64, nanopb_pb2.IS_32):   ('int32_t', 'SINT64',  5,  4),
    (FieldD.TYPE_SINT64, nanopb_pb2.IS_64):   ('int64_t', 'SINT64', 10,  8),
    (FieldD.TYPE_UINT64,  nanopb_pb2.IS_8):   ('uint8_t', 'UINT64',  2,  1),
    (FieldD.TYPE_UINT64, nanopb_pb2.IS_16):   ('uint16_t','UINT64',  3,  2),
    (FieldD.TYPE_UINT64, nanopb_pb2.IS_32):   ('uint32_t','UINT64',  5,  4),
    (FieldD.TYPE_UINT64, nanopb_pb2.IS_64):   ('uint64_t','UINT64', 10,  8),
}

# String types (for python 2 / python 3 compatibility)
try:
    strtypes = (unicode, str)
except NameError:
    strtypes = (str, )


class Names:
    '''Keeps a set of nested names and formats them to C identifier.'''
    def __init__(self, parts = ()):
        if isinstance(parts, Names):
            parts = parts.parts
        elif isinstance(parts, strtypes):
            parts = (parts,)
        self.parts = tuple(parts)

    def __str__(self):
        return '_'.join(self.parts)

    def __add__(self, other):
        if isinstance(other, strtypes):
            return Names(self.parts + (other,))
        elif isinstance(other, Names):
            return Names(self.parts + other.parts)
        elif isinstance(other, tuple):
            return Names(self.parts + other)
        else:
            raise ValueError("Name parts should be of type str")

    def __eq__(self, other):
        return isinstance(other, Names) and self.parts == other.parts

def names_from_type_name(type_name):
    '''Parse Names() from FieldDescriptorProto type_name'''
    if type_name[0] != '.':
        raise NotImplementedError("Lookup of non-absolute type names is not supported")
    return Names(type_name[1:].split('.'))

def varint_max_size(max_value):
    '''Returns the maximum number of bytes a varint can take when encoded.'''
    if max_value < 0:
        max_value = 2**64 - max_value
    for i in range(1, 11):
        if (max_value >> (i * 7)) == 0:
            return i
    raise ValueError("Value too large for varint: " + str(max_value))

assert varint_max_size(-1) == 10
assert varint_max_size(0) == 1
assert varint_max_size(127) == 1
assert varint_max_size(128) == 2

class EncodedSize:
    '''Class used to represent the encoded size of a field or a message.
    Consists of a combination of symbolic sizes and integer sizes.'''
    def __init__(self, value = 0, symbols = []):
        if isinstance(value, EncodedSize):
            self.value = value.value
            self.symbols = value.symbols
        elif isinstance(value, strtypes + (Names,)):
            self.symbols = [str(value)]
            self.value = 0
        else:
            self.value = value
            self.symbols = symbols

    def __add__(self, other):
        if isinstance(other, int):
            return EncodedSize(self.value + other, self.symbols)
        elif isinstance(other, strtypes + (Names,)):
            return EncodedSize(self.value, self.symbols + [str(other)])
        elif isinstance(other, EncodedSize):
            return EncodedSize(self.value + other.value, self.symbols + other.symbols)
        else:
            raise ValueError("Cannot add size: " + repr(other))

    def __mul__(self, other):
        if isinstance(other, int):
            return EncodedSize(self.value * other, [str(other) + '*' + s for s in self.symbols])
        else:
            raise ValueError("Cannot multiply size: " + repr(other))

    def __str__(self):
        if not self.symbols:
            return str(self.value)
        else:
            return '(' + str(self.value) + ' + ' + ' + '.join(self.symbols) + ')'

    def upperlimit(self):
        if not self.symbols:
            return self.value
        else:
            return 2**32 - 1

class Enum:
    def __init__(self, names, desc, enum_options):
        '''desc is EnumDescriptorProto'''

        self.options = enum_options
        self.names = names

        # by definition, `names` include this enum's name
        base_name = Names(names.parts[:-1])

        if enum_options.long_names:
            self.values = [(names + x.name, x.number) for x in desc.value]
        else:
            self.values = [(base_name + x.name, x.number) for x in desc.value]

        self.value_longnames = [self.names + x.name for x in desc.value]
        self.packed = enum_options.packed_enum

    def has_negative(self):
        for n, v in self.values:
            if v < 0:
                return True
        return False

    def encoded_size(self):
        return max([varint_max_size(v) for n,v in self.values])

    def __str__(self):
        result = 'typedef enum _%s {\n' % self.names
        result += ',\n'.join(["    %s = %d" % x for x in self.values])
        result += '\n}'

        if self.packed:
            result += ' pb_packed'

        result += ' %s;' % self.names

        # sort the enum by value
        sorted_values = sorted(self.values, key = lambda x: (x[1], x[0]))

        result += '\n#define _%s_MIN %s' % (self.names, sorted_values[0][0])
        result += '\n#define _%s_MAX %s' % (self.names, sorted_values[-1][0])
        result += '\n#define _%s_ARRAYSIZE ((%s)(%s+1))' % (self.names, self.names, sorted_values[-1][0])

        if not self.options.long_names:
            # Define the long names always so that enum value references
            # from other files work properly.
            for i, x in enumerate(self.values):
                result += '\n#define %s %s' % (self.value_longnames[i], x[0])

        if self.options.enum_to_string:
            result += '\nconst char *%s_name(%s v);\n' % (self.names, self.names)

        return result

    def enum_to_string_definition(self):
        if not self.options.enum_to_string:
            return ""

        result = 'const char *%s_name(%s v) {\n' % (self.names, self.names)
        result += '    switch (v) {\n'

        for ((enumname, _), strname) in zip(self.values, self.value_longnames):
            # Strip off the leading type name from the string value.
            strval = str(strname)[len(str(self.names)) + 1:]
            result += '        case %s: return "%s";\n' % (enumname, strval)

        result += '    }\n'
        result += '    return "unknown";\n'
        result += '}\n'

        return result

class FieldMaxSize:
    def __init__(self, worst = 0, checks = [], field_name = 'undefined'):
        if isinstance(worst, list):
            self.worst = max(i for i in worst if i is not None)
        else:
            self.worst = worst

        self.worst_field = field_name
        self.checks = list(checks)

    def extend(self, extend, field_name = None):
        self.worst = max(self.worst, extend.worst)

        if self.worst == extend.worst:
            self.worst_field = extend.worst_field

        self.checks.extend(extend.checks)

class Field:
    def __init__(self, struct_name, desc, field_options):
        '''desc is FieldDescriptorProto'''
        self.tag = desc.number
        self.struct_name = struct_name
        self.union_name = None
        self.name = desc.name
        self.default = None
        self.max_size = None
        self.max_count = None
        self.array_decl = ""
        self.enc_size = None
        self.data_item_size = None
        self.ctype = None
        self.fixed_count = False
        self.callback_datatype = field_options.callback_datatype

        if field_options.type == nanopb_pb2.FT_INLINE:
            # Before nanopb-0.3.8, fixed length bytes arrays were specified
            # by setting type to FT_INLINE. But to handle pointer typed fields,
            # it makes sense to have it as a separate option.
            field_options.type = nanopb_pb2.FT_STATIC
            field_options.fixed_length = True

        # Parse field options
        if field_options.HasField("max_size"):
            self.max_size = field_options.max_size

        if desc.type == FieldD.TYPE_STRING and field_options.HasField("max_length"):
            # max_length overrides max_size for strings
            self.max_size = field_options.max_length + 1

        if field_options.HasField("max_count"):
            self.max_count = field_options.max_count

        if desc.HasField('default_value'):
            self.default = desc.default_value

        # Check field rules, i.e. required/optional/repeated.
        can_be_static = True
        if desc.label == FieldD.LABEL_REPEATED:
            self.rules = 'REPEATED'
            if self.max_count is None:
                can_be_static = False
            else:
                self.array_decl = '[%d]' % self.max_count
                if field_options.fixed_count:
                  self.rules = 'FIXARRAY'

        elif field_options.proto3:
            self.rules = 'SINGULAR'
        elif desc.label == FieldD.LABEL_REQUIRED:
            self.rules = 'REQUIRED'
        elif desc.label == FieldD.LABEL_OPTIONAL:
            self.rules = 'OPTIONAL'
        else:
            raise NotImplementedError(desc.label)

        # Check if the field can be implemented with static allocation
        # i.e. whether the data size is known.
        if desc.type == FieldD.TYPE_STRING and self.max_size is None:
            can_be_static = False

        if desc.type == FieldD.TYPE_BYTES and self.max_size is None:
            can_be_static = False

        # Decide how the field data will be allocated
        if field_options.type == nanopb_pb2.FT_DEFAULT:
            if can_be_static:
                field_options.type = nanopb_pb2.FT_STATIC
            else:
                field_options.type = nanopb_pb2.FT_CALLBACK

        if field_options.type == nanopb_pb2.FT_STATIC and not can_be_static:
            raise Exception("Field '%s' is defined as static, but max_size or "
                            "max_count is not given." % self.name)

        if field_options.fixed_count and self.max_count is None:
            raise Exception("Field '%s' is defined as fixed count, "
                            "but max_count is not given." % self.name)

        if field_options.type == nanopb_pb2.FT_STATIC:
            self.allocation = 'STATIC'
        elif field_options.type == nanopb_pb2.FT_POINTER:
            self.allocation = 'POINTER'
        elif field_options.type == nanopb_pb2.FT_CALLBACK:
            self.allocation = 'CALLBACK'
        else:
            raise NotImplementedError(field_options.type)

        # Decide the C data type to use in the struct.
        if desc.type in datatypes:
            self.ctype, self.pbtype, self.enc_size, self.data_item_size = datatypes[desc.type]

            # Override the field size if user wants to use smaller integers
            if (desc.type, field_options.int_size) in datatypes:
                self.ctype, self.pbtype, self.enc_size, self.data_item_size = datatypes[(desc.type, field_options.int_size)]
        elif desc.type == FieldD.TYPE_ENUM:
            self.pbtype = 'ENUM'
            self.data_item_size = 4
            self.ctype = names_from_type_name(desc.type_name)
            if self.default is not None:
                self.default = self.ctype + self.default
            self.enc_size = None # Needs to be filled in when enum values are known
        elif desc.type == FieldD.TYPE_STRING:
            self.pbtype = 'STRING'
            self.ctype = 'char'
            if self.allocation == 'STATIC':
                self.ctype = 'char'
                self.array_decl += '[%d]' % self.max_size
                # -1 because of null terminator. Both pb_encode and pb_decode
                # check the presence of it.
                self.enc_size = varint_max_size(self.max_size) + self.max_size - 1
        elif desc.type == FieldD.TYPE_BYTES:
            if field_options.fixed_length:
                self.pbtype = 'FIXED_LENGTH_BYTES'

                if self.max_size is None:
                    raise Exception("Field '%s' is defined as fixed length, "
                                    "but max_size is not given." % self.name)

                self.enc_size = varint_max_size(self.max_size) + self.max_size
                self.ctype = 'pb_byte_t'
                self.array_decl += '[%d]' % self.max_size
            else:
                self.pbtype = 'BYTES'
                self.ctype = 'pb_bytes_array_t'
                if self.allocation == 'STATIC':
                    self.ctype = self.struct_name + self.name + 't'
                    self.enc_size = varint_max_size(self.max_size) + self.max_size
        elif desc.type == FieldD.TYPE_MESSAGE:
            self.pbtype = 'MESSAGE'
            self.ctype = self.submsgname = names_from_type_name(desc.type_name)
            self.enc_size = None # Needs to be filled in after the message type is available
        else:
            raise NotImplementedError(desc.type)

    def __lt__(self, other):
        return self.tag < other.tag

    def __str__(self):
        result = ''
        if self.allocation == 'POINTER':
            if self.rules == 'REPEATED':
                result += '    pb_size_t ' + self.name + '_count;\n'

            if self.pbtype == 'MESSAGE':
                # Use struct definition, so recursive submessages are possible
                result += '    struct _%s *%s;' % (self.ctype, self.name)
            elif self.pbtype == 'FIXED_LENGTH_BYTES':
                # Pointer to fixed size array
                result += '    %s (*%s)%s;' % (self.ctype, self.name, self.array_decl)
            elif self.rules in ['REPEATED', 'FIXARRAY'] and self.pbtype in ['STRING', 'BYTES']:
                # String/bytes arrays need to be defined as pointers to pointers
                result += '    %s **%s;' % (self.ctype, self.name)
            else:
                result += '    %s *%s;' % (self.ctype, self.name)
        elif self.allocation == 'CALLBACK':
            result += '    %s %s;' % (self.callback_datatype, self.name)
        else:
            if self.rules == 'OPTIONAL':
                result += '    bool has_' + self.name + ';\n'
            elif self.rules == 'REPEATED':
                result += '    pb_size_t ' + self.name + '_count;\n'
            result += '    %s %s%s;' % (self.ctype, self.name, self.array_decl)
        return result

    def types(self):
        '''Return definitions for any special types this field might need.'''
        if self.pbtype == 'BYTES' and self.allocation == 'STATIC':
            result = 'typedef PB_BYTES_ARRAY_T(%d) %s;\n' % (self.max_size, self.ctype)
        else:
            result = ''
        return result

    def get_dependencies(self):
        '''Get list of type names used by this field.'''
        if self.allocation == 'STATIC':
            return [str(self.ctype)]
        else:
            return []

    def get_initializer(self, null_init, inner_init_only = False):
        '''Return literal expression for this field's default value.
        null_init: If True, initialize to a 0 value instead of default from .proto
        inner_init_only: If True, exclude initialization for any count/has fields
        '''

        inner_init = None
        if self.pbtype == 'MESSAGE':
            if null_init:
                inner_init = '%s_init_zero' % self.ctype
            else:
                inner_init = '%s_init_default' % self.ctype
        elif self.default is None or null_init:
            if self.pbtype == 'STRING':
                inner_init = '""'
            elif self.pbtype == 'BYTES':
                inner_init = '{0, {0}}'
            elif self.pbtype == 'FIXED_LENGTH_BYTES':
                inner_init = '{0}'
            elif self.pbtype in ('ENUM', 'UENUM'):
                inner_init = '_%s_MIN' % self.ctype
            else:
                inner_init = '0'
        else:
            if self.pbtype == 'STRING':
                data = codecs.escape_encode(self.default.encode('utf-8'))[0]
                inner_init = '"' + data.decode('ascii') + '"'
            elif self.pbtype == 'BYTES':
                data = codecs.escape_decode(self.default)[0]
                data = ["0x%02x" % c for c in bytearray(data)]
                if len(data) == 0:
                    inner_init = '{0, {0}}'
                else:
                    inner_init = '{%d, {%s}}' % (len(data), ','.join(data))
            elif self.pbtype == 'FIXED_LENGTH_BYTES':
                data = codecs.escape_decode(self.default)[0]
                data = ["0x%02x" % c for c in bytearray(data)]
                if len(data) == 0:
                    inner_init = '{0}'
                else:
                    inner_init = '{%s}' % ','.join(data)
            elif self.pbtype in ['FIXED32', 'UINT32']:
                inner_init = str(self.default) + 'u'
            elif self.pbtype in ['FIXED64', 'UINT64']:
                inner_init = str(self.default) + 'ull'
            elif self.pbtype in ['SFIXED64', 'INT64']:
                inner_init = str(self.default) + 'll'
            else:
                inner_init = str(self.default)

        if inner_init_only:
            return inner_init

        outer_init = None
        if self.allocation == 'STATIC':
            if self.rules == 'REPEATED':
                outer_init = '0, {' + ', '.join([inner_init] * self.max_count) + '}'
            elif self.rules == 'FIXARRAY':
                outer_init = '{' + ', '.join([inner_init] * self.max_count) + '}'
            elif self.rules == 'OPTIONAL':
                outer_init = 'false, ' + inner_init
            else:
                outer_init = inner_init
        elif self.allocation == 'POINTER':
            if self.rules == 'REPEATED':
                outer_init = '0, NULL'
            else:
                outer_init = 'NULL'
        elif self.allocation == 'CALLBACK':
            if self.pbtype == 'EXTENSION':
                outer_init = 'NULL'
            else:
                outer_init = '{{NULL}, NULL}'

        return outer_init

    def tags(self):
        '''Return the #define for the tag number of this field.'''
        identifier = '%s_%s_tag' % (self.struct_name, self.name)
        return '#define %-40s %d\n' % (identifier, self.tag)

    def fieldlist(self):
        '''Return the FIELDLIST macro entry for this field.
        Format is: X(a, ATYPE, HTYPE, LTYPE, field_name, tag)
        '''
        name = self.name

        if self.rules == "ONEOF":
          # For oneofs, make a tuple of the union name, union member name,
          # and the name inside the parent struct.
          if not self.anonymous:
            name = '(%s,%s,%s)' % (self.union_name, self.name, self.union_name + '.' + self.name)
          else:
            name = '(%s,%s,%s)' % (self.union_name, self.name, self.name)

        return 'X(a, %s, %s, %s, %s, %d)' % (self.allocation, self.rules, self.pbtype, name, self.tag)

    def data_size(self, dependencies):
        '''Return estimated size of this field in the C struct.
        This is used to try to automatically pick right descriptor size.
        If the estimate is wrong, it will result in compile time error and
        user having to specify descriptor_width option.
        '''
        if self.allocation == 'POINTER' or self.pbtype == 'EXTENSION':
            size = 8
        elif self.allocation == 'CALLBACK':
            size = 16
        elif self.pbtype == 'MESSAGE':
            if str(self.submsgname) in dependencies:
                size = dependencies[str(self.submsgname)].data_size(dependencies)
            else:
                size = 256 # Message is in other file, this is reasonable guess for most cases
        elif self.pbtype in ['STRING', 'FIXED_LENGTH_BYTES']:
            size = self.max_size
        elif self.pbtype == 'BYTES':
            size = self.max_size + 4
        elif self.data_item_size is not None:
            size = self.data_item_size
        else:
            raise Exception("Unhandled field type: %s" % self.pbtype)

        if self.rules in ['REPEATED', 'FIXARRAY'] and self.allocation == 'STATIC':
            size *= self.max_count

        if self.rules not in ('REQUIRED', 'SINGULAR'):
            size += 4

        if size % 4 != 0:
            # Estimate how much alignment requirements will increase the size.
            size += 4 - (size % 4)

        return size

    def encoded_size(self, dependencies):
        '''Return the maximum size that this field can take when encoded,
        including the field tag. If the size cannot be determined, returns
        None.'''

        if self.allocation != 'STATIC':
            return None

        if self.pbtype == 'MESSAGE':
            encsize = None
            if str(self.submsgname) in dependencies:
                submsg = dependencies[str(self.submsgname)]
                encsize = submsg.encoded_size(dependencies)
                if encsize is not None:
                    # Include submessage length prefix
                    encsize += varint_max_size(encsize.upperlimit())
                else:
                    my_msg = dependencies.get(str(self.struct_name))
                    if my_msg and submsg.protofile == my_msg.protofile:
                        # The dependency is from the same file and size cannot be
                        # determined for it, thus we know it will not be possible
                        # in runtime either.
                        return None

            if encsize is None:
                # Submessage or its size cannot be found.
                # This can occur if submessage is defined in different
                # file, and it or its .options could not be found.
                # Instead of direct numeric value, reference the size that
                # has been #defined in the other file.
                encsize = EncodedSize(self.submsgname + 'size')

                # We will have to make a conservative assumption on the length
                # prefix size, though.
                encsize += 5

        elif self.pbtype in ['ENUM', 'UENUM']:
            if str(self.ctype) in dependencies:
                enumtype = dependencies[str(self.ctype)]
                encsize = enumtype.encoded_size()
            else:
                # Conservative assumption
                encsize = 10

        elif self.enc_size is None:
            raise RuntimeError("Could not determine encoded size for %s.%s"
                               % (self.struct_name, self.name))
        else:
            encsize = EncodedSize(self.enc_size)

        encsize += varint_max_size(self.tag << 3) # Tag + wire type

        if self.rules in ['REPEATED', 'FIXARRAY']:
            # Decoders must be always able to handle unpacked arrays.
            # Therefore we have to reserve space for it, even though
            # we emit packed arrays ourselves. For length of 1, packed
            # arrays are larger however so we need to add allowance
            # for the length byte.
            encsize *= self.max_count

            if self.max_count == 1:
                encsize += 1

        return encsize

    def requires_custom_field_callback(self):
        if self.allocation == 'CALLBACK' and self.callback_datatype != 'pb_callback_t':
            return True
        else:
            return False


class ExtensionRange(Field):
    def __init__(self, struct_name, range_start, field_options):
        '''Implements a special pb_extension_t* field in an extensible message
        structure. The range_start signifies the index at which the extensions
        start. Not necessarily all tags above this are extensions, it is merely
        a speed optimization.
        '''
        self.tag = range_start
        self.struct_name = struct_name
        self.name = 'extensions'
        self.pbtype = 'EXTENSION'
        self.rules = 'OPTIONAL'
        self.allocation = 'CALLBACK'
        self.ctype = 'pb_extension_t'
        self.array_decl = ''
        self.default = None
        self.max_size = 0
        self.max_count = 0
        self.data_item_size = 0
        self.fixed_count = False
        self.callback_datatype = 'pb_extension_t*'

    def requires_custom_field_callback(self):
        return False

    def __str__(self):
        return '    pb_extension_t *extensions;'

    def types(self):
        return ''

    def tags(self):
        return ''

    def encoded_size(self, dependencies):
        # We exclude extensions from the count, because they cannot be known
        # until runtime. Other option would be to return None here, but this
        # way the value remains useful if extensions are not used.
        return EncodedSize(0)

class ExtensionField(Field):
    def __init__(self, fullname, desc, field_options):
        self.fullname = fullname
        self.extendee_name = names_from_type_name(desc.extendee)
        Field.__init__(self, self.fullname + "extmsg", desc, field_options)

        if self.rules != 'OPTIONAL':
            self.skip = True
        else:
            self.skip = False
            self.rules = 'REQUIRED' # We don't really want the has_field for extensions
            self.msg = Message(self.fullname + "extmsg", None, field_options)
            self.msg.fields.append(self)

    def tags(self):
        '''Return the #define for the tag number of this field.'''
        identifier = '%s_tag' % self.fullname
        return '#define %-40s %d\n' % (identifier, self.tag)

    def extension_decl(self):
        '''Declaration of the extension type in the .pb.h file'''
        if self.skip:
            msg = '/* Extension field %s was skipped because only "optional"\n' % self.fullname
            msg +='   type of extension fields is currently supported. */\n'
            return msg

        return ('extern const pb_extension_type_t %s; /* field type: %s */\n' %
            (self.fullname, str(self).strip()))

    def extension_def(self, dependencies):
        '''Definition of the extension type in the .pb.c file'''

        if self.skip:
            return ''

        result = "/* Definition for extension field %s */\n" % self.fullname
        result += str(self.msg)
        result += self.msg.fields_declaration(dependencies)
        result += 'pb_byte_t %s_default[] = {0x00};\n' % self.msg.name
        result += self.msg.fields_definition(dependencies)
        result += 'const pb_extension_type_t %s = {\n' % self.fullname
        result += '    NULL,\n'
        result += '    NULL,\n'
        result += '    &%s_msg\n' % self.msg.name
        result += '};\n'
        return result


# ---------------------------------------------------------------------------
#                   Generation of oneofs (unions)
# ---------------------------------------------------------------------------

class OneOf(Field):
    def __init__(self, struct_name, oneof_desc):
        self.struct_name = struct_name
        self.name = oneof_desc.name
        self.ctype = 'union'
        self.pbtype = 'oneof'
        self.fields = []
        self.allocation = 'ONEOF'
        self.default = None
        self.rules = 'ONEOF'
        self.anonymous = False

    def add_field(self, field):
        if field.allocation == 'CALLBACK':
            raise Exception("Callback fields inside of oneof are not supported"
                            + " (field %s)" % field.name)

        field.union_name = self.name
        field.rules = 'ONEOF'
        field.anonymous = self.anonymous
        self.fields.append(field)
        self.fields.sort(key = lambda f: f.tag)

        # Sort by the lowest tag number inside union
        self.tag = min([f.tag for f in self.fields])

    def __str__(self):
        result = ''
        if self.fields:
            result += '    pb_size_t which_' + self.name + ";\n"
            result += '    union {\n'
            for f in self.fields:
                result += '    ' + str(f).replace('\n', '\n    ') + '\n'
            if self.anonymous:
                result += '    };'
            else:
                result += '    } ' + self.name + ';'
        return result

    def types(self):
        return ''.join([f.types() for f in self.fields])

    def get_dependencies(self):
        deps = []
        for f in self.fields:
            deps += f.get_dependencies()
        return deps

    def get_initializer(self, null_init):
        return '0, {' + self.fields[0].get_initializer(null_init) + '}'

    def tags(self):
        return ''.join([f.tags() for f in self.fields])

    def fieldlist(self):
        return ' \\\n'.join(field.fieldlist() for field in self.fields)

    def data_size(self, dependencies):
        return max(f.data_size(dependencies) for f in self.fields)

    def encoded_size(self, dependencies):
        '''Returns the size of the largest oneof field.'''
        largest = 0
        symbols = []
        for f in self.fields:
            size = EncodedSize(f.encoded_size(dependencies))
            if size is None or size.value is None:
                return None
            elif size.symbols:
                symbols.append((f.tag, size.symbols[0]))
            elif size.value > largest:
                largest = size.value

        if not symbols:
            # Simple case, all sizes were known at generator time
            return largest

        if largest > 0:
            # Some sizes were known, some were not
            symbols.insert(0, (0, largest))

        if len(symbols) == 1:
            # Only one symbol was needed
            return EncodedSize(5, [symbols[0][1]])
        else:
            # Use sizeof(union{}) construct to find the maximum size of
            # submessages.
            union_def = ' '.join('char f%d[%s];' % s for s in symbols)
            return EncodedSize(5, ['sizeof(union{%s})' % union_def])

# ---------------------------------------------------------------------------
#                   Generation of messages (structures)
# ---------------------------------------------------------------------------


class Message:
    def __init__(self, names, desc, message_options):
        self.name = names
        self.fields = []
        self.oneofs = {}
        self.desc = desc

        if message_options.msgid:
            self.msgid = message_options.msgid

        if desc is not None:
            self.load_fields(desc, message_options)

        self.callback_function = message_options.callback_function
        if not message_options.HasField('callback_function'):
            # Automatically assign a per-message callback if any field has
            # a special callback_datatype.
            for field in self.fields:
                if field.requires_custom_field_callback():
                    self.callback_function = "%s_callback" % self.name
                    break

        self.packed = message_options.packed_struct
        self.descriptorsize = message_options.descriptorsize

    def load_fields(self, desc, message_options):
        '''Load field list from DescriptorProto'''

        no_unions = []

        if hasattr(desc, 'oneof_decl'):
            for i, f in enumerate(desc.oneof_decl):
                oneof_options = get_nanopb_suboptions(desc, message_options, self.name + f.name)
                if oneof_options.no_unions:
                    no_unions.append(i) # No union, but add fields normally
                elif oneof_options.type == nanopb_pb2.FT_IGNORE:
                    pass # No union and skip fields also
                else:
                    oneof = OneOf(self.name, f)
                    if oneof_options.anonymous_oneof:
                        oneof.anonymous = True
                    self.oneofs[i] = oneof
                    self.fields.append(oneof)
        else:
            sys.stderr.write('Note: This Python protobuf library has no OneOf support\n')

        for f in desc.field:
            field_options = get_nanopb_suboptions(f, message_options, self.name + f.name)
            if field_options.type == nanopb_pb2.FT_IGNORE:
                continue

            field = Field(self.name, f, field_options)
            if (hasattr(f, 'oneof_index') and
                f.HasField('oneof_index') and
                f.oneof_index not in no_unions):
                if f.oneof_index in self.oneofs:
                    self.oneofs[f.oneof_index].add_field(field)
            else:
                self.fields.append(field)

        if len(desc.extension_range) > 0:
            field_options = get_nanopb_suboptions(desc, message_options, self.name + 'extensions')
            range_start = min([r.start for r in desc.extension_range])
            if field_options.type != nanopb_pb2.FT_IGNORE:
                self.fields.append(ExtensionRange(self.name, range_start, field_options))

    def get_dependencies(self):
        '''Get list of type names that this structure refers to.'''
        deps = []
        for f in self.fields:
            deps += f.get_dependencies()
        return deps

    def __str__(self):
        result = 'typedef struct _%s {\n' % self.name

        if not self.fields:
            # Empty structs are not allowed in C standard.
            # Therefore add a dummy field if an empty message occurs.
            result += '    char dummy_field;'

        result += '\n'.join([str(f) for f in sorted(self.fields)])
        result += '\n/* @@protoc_insertion_point(struct:%s) */' % self.name
        result += '\n}'

        if self.packed:
            result += ' pb_packed'

        result += ' %s;' % self.name

        if self.packed:
            result = 'PB_PACKED_STRUCT_START\n' + result
            result += '\nPB_PACKED_STRUCT_END'

        return result + '\n'

    def types(self):
        return ''.join([f.types() for f in self.fields])

    def get_initializer(self, null_init):
        if not self.fields:
            return '{0}'

        parts = []
        for field in sorted(self.fields):
            parts.append(field.get_initializer(null_init))
        return '{' + ', '.join(parts) + '}'

    def count_required_fields(self):
        '''Returns number of required fields inside this message'''
        count = 0
        for f in self.fields:
            if not isinstance(f, OneOf):
                if f.rules == 'REQUIRED':
                    count += 1
        return count

    def all_fields(self):
        '''Iterate over all fields in this message, including nested OneOfs.'''
        for f in self.fields:
            if isinstance(f, OneOf):
                for f2 in f.fields:
                    yield f2
            else:
                yield f


    def field_for_tag(self, tag):
        '''Given a tag number, return the Field instance.'''
        for field in self.all_fields():
            if field.tag == tag:
                return field
        return None

    def count_all_fields(self):
        '''Count the total number of fields in this message.'''
        count = 0
        for f in self.fields:
            if isinstance(f, OneOf):
                count += len(f.fields)
            else:
                count += 1
        return count

    def fields_declaration(self, dependencies):
        '''Return X-macro declaration of all fields in this message.'''
        result = '#define %s_FIELDLIST(X, a) \\\n' % (self.name)
        result += ' \\\n'.join(field.fieldlist() for field in sorted(self.fields))
        result += '\n'

        has_callbacks = bool([f for f in self.fields if f.allocation == 'CALLBACK'])
        if has_callbacks:
            if self.callback_function != 'pb_default_field_callback':
                result += "extern bool %s(pb_istream_t *istream, pb_ostream_t *ostream, const pb_field_t *field);\n" % self.callback_function
            result += "#define %s_CALLBACK %s\n" % (self.name, self.callback_function)
        else:
            result += "#define %s_CALLBACK NULL\n" % self.name

        defval = self.default_value(dependencies)
        if defval:
            hexcoded = ''.join("\\x%02x" % ord(defval[i:i+1]) for i in range(len(defval)))
            result += '#define %s_DEFAULT (const uint8_t*)"%s\\x00"\n' % (self.name, hexcoded)
        else:
            result += '#define %s_DEFAULT NULL\n' % self.name

        for field in sorted(self.fields):
            if field.pbtype == 'MESSAGE':
                result += "#define %s_%s_MSGTYPE %s\n" % (self.name, field.name, field.ctype)
            elif field.rules == 'ONEOF':
                for member in field.fields:
                    if member.pbtype == 'MESSAGE':
                        result += "#define %s_%s_%s_MSGTYPE %s\n" % (self.name, member.union_name, member.name, member.ctype)

        return result

    def fields_declaration_cpp_lookup(self):
        result = 'template <>\n'
        result += 'struct MessageDescriptor<%s> {\n' % (self.name)
        result += '    static PB_INLINE_CONSTEXPR const pb_size_t fields_array_length = %d;\n' % (self.count_all_fields())
        result += '    static inline const pb_msgdesc_t* fields() {\n'
        result += '        return &%s_msg;\n' % (self.name)
        result += '    }\n'
        result += '};'
        return result

    def fields_definition(self, dependencies):
        '''Return the field descriptor definition that goes in .pb.c file.'''
        width = self.required_descriptor_width(dependencies)
        if width == 1:
          width = 'AUTO'

        result = 'PB_BIND(%s, %s, %s)\n' % (self.name, self.name, width)
        return result

    def required_descriptor_width(self, dependencies):
        '''Estimate how many words are necessary for each field descriptor.'''
        if self.descriptorsize != nanopb_pb2.DS_AUTO:
            return int(self.descriptorsize)

        if not self.fields:
          return 1

        max_tag = max(field.tag for field in self.all_fields())
        max_offset = self.data_size(dependencies)
        max_arraysize = max((field.max_count or 0) for field in self.all_fields())
        max_datasize = max(field.data_size(dependencies) for field in self.all_fields())

        if max_arraysize > 0xFFFF:
            return 8
        elif (max_tag > 0x3FF or max_offset > 0xFFFF or
              max_arraysize > 0x0FFF or max_datasize > 0x0FFF):
            return 4
        elif max_tag > 0x3F or max_offset > 0xFF:
            return 2
        else:
            # NOTE: Macro logic in pb.h ensures that width 1 will
            # be raised to 2 automatically for string/submsg fields
            # and repeated fields. Thus only tag and offset need to
            # be checked.
            return 1

    def data_size(self, dependencies):
        '''Return approximate sizeof(struct) in the compiled code.'''
        return sum(f.data_size(dependencies) for f in self.fields)

    def encoded_size(self, dependencies):
        '''Return the maximum size that this message can take when encoded.
        If the size cannot be determined, returns None.
        '''
        size = EncodedSize(0)
        for field in self.fields:
            fsize = field.encoded_size(dependencies)
            if fsize is None:
                return None
            size += fsize

        return size

    def default_value(self, dependencies):
        '''Generate serialized protobuf message that contains the
        default values for optional fields.'''

        if not self.desc:
            return b''

        if self.desc.options.map_entry:
            return b''

        optional_only = copy.deepcopy(self.desc)
        enums = []

        # Remove fields without default values
        # The iteration is done in reverse order to avoid remove() messing up iteration.
        for field in reversed(list(optional_only.field)):
            parsed_field = self.field_for_tag(field.number)
            if parsed_field is None or parsed_field.allocation != 'STATIC':
                optional_only.field.remove(field)
            elif (field.label == FieldD.LABEL_REPEATED or
                  field.type == FieldD.TYPE_MESSAGE or
                  not field.HasField('default_value')):
                optional_only.field.remove(field)
            elif hasattr(field, 'oneof_index') and field.HasField('oneof_index'):
                optional_only.field.remove(field)
            elif field.type == FieldD.TYPE_ENUM:
                # The partial descriptor doesn't include the enum type
                # so we fake it with int64.
                enums.append(field.name)
                field.type = FieldD.TYPE_INT64

        if len(optional_only.field) == 0:
            return b''

        optional_only.ClearField(str('oneof_decl'))
        desc = google.protobuf.descriptor.MakeDescriptor(optional_only)
        msg = reflection.MakeClass(desc)()

        for field in optional_only.field:
            if field.type == FieldD.TYPE_STRING:
                setattr(msg, field.name, field.default_value)
            elif field.type == FieldD.TYPE_BYTES:
                setattr(msg, field.name, codecs.escape_decode(field.default_value)[0])
            elif field.type in [FieldD.TYPE_FLOAT, FieldD.TYPE_DOUBLE]:
                setattr(msg, field.name, float(field.default_value))
            elif field.type == FieldD.TYPE_BOOL:
                setattr(msg, field.name, field.default_value == 'true')
            elif field.name in enums:
                # Lookup the enum default value
                enumname = names_from_type_name(field.type_name)
                enumtype = dependencies[str(enumname)]
                defvals = [v for n,v in enumtype.values if n.parts[-1] == field.default_value]
                if defvals:
                    setattr(msg, field.name, defvals[0])
            else:
                setattr(msg, field.name, int(field.default_value))

        return msg.SerializeToString()


# ---------------------------------------------------------------------------
#                    Processing of entire .proto files
# ---------------------------------------------------------------------------

def iterate_messages(desc, flatten = False, names = Names()):
    '''Recursively find all messages. For each, yield name, DescriptorProto.'''
    if hasattr(desc, 'message_type'):
        submsgs = desc.message_type
    else:
        submsgs = desc.nested_type

    for submsg in submsgs:
        sub_names = names + submsg.name
        if flatten:
            yield Names(submsg.name), submsg
        else:
            yield sub_names, submsg

        for x in iterate_messages(submsg, flatten, sub_names):
            yield x

def iterate_extensions(desc, flatten = False, names = Names()):
    '''Recursively find all extensions.
    For each, yield name, FieldDescriptorProto.
    '''
    for extension in desc.extension:
        yield names, extension

    for subname, subdesc in iterate_messages(desc, flatten, names):
        for extension in subdesc.extension:
            yield subname, extension

def toposort2(data):
    '''Topological sort.
    From http://code.activestate.com/recipes/577413-topological-sort/
    This function is under the MIT license.
    '''
    for k, v in list(data.items()):
        v.discard(k) # Ignore self dependencies
    extra_items_in_deps = reduce(set.union, list(data.values()), set()) - set(data.keys())
    data.update(dict([(item, set()) for item in extra_items_in_deps]))
    while True:
        ordered = set(item for item,dep in list(data.items()) if not dep)
        if not ordered:
            break
        for item in sorted(ordered):
            yield item
        data = dict([(item, (dep - ordered)) for item,dep in list(data.items())
                if item not in ordered])
    assert not data, "A cyclic dependency exists amongst %r" % data

def sort_dependencies(messages):
    '''Sort a list of Messages based on dependencies.'''
    dependencies = {}
    message_by_name = {}
    for message in messages:
        dependencies[str(message.name)] = set(message.get_dependencies())
        message_by_name[str(message.name)] = message

    for msgname in toposort2(dependencies):
        if msgname in message_by_name:
            yield message_by_name[msgname]

def make_identifier(headername):
    '''Make #ifndef identifier that contains uppercase A-Z and digits 0-9'''
    result = ""
    for c in headername.upper():
        if c.isalnum():
            result += c
        else:
            result += '_'
    return result

class ProtoFile:
    def __init__(self, fdesc, file_options):
        '''Takes a FileDescriptorProto and parses it.'''
        self.fdesc = fdesc
        self.file_options = file_options
        self.dependencies = {}
        self.parse()

        # Some of types used in this file probably come from the file itself.
        # Thus it has implicit dependency on itself.
        self.add_dependency(self)

    def parse(self):
        self.enums = []
        self.messages = []
        self.extensions = []

        mangle_names = self.file_options.mangle_names
        flatten = mangle_names == nanopb_pb2.M_FLATTEN
        strip_prefix = None
        replacement_prefix = None
        if mangle_names == nanopb_pb2.M_STRIP_PACKAGE:
            strip_prefix = "." + self.fdesc.package
        elif mangle_names == nanopb_pb2.M_PACKAGE_INITIALS:
            strip_prefix = "." + self.fdesc.package
            replacement_prefix = ""
            for part in self.fdesc.package.split("."):
                replacement_prefix += part[0]

        def create_name(names):
            if mangle_names == nanopb_pb2.M_NONE or mangle_names == nanopb_pb2.M_PACKAGE_INITIALS:
                return base_name + names
            elif mangle_names == nanopb_pb2.M_STRIP_PACKAGE:
                return Names(names)
            else:
                single_name = names
                if isinstance(names, Names):
                    single_name = names.parts[-1]
                return Names(single_name)

        def mangle_field_typename(typename):
            if mangle_names == nanopb_pb2.M_FLATTEN:
                return "." + typename.split(".")[-1]
            elif strip_prefix is not None and typename.startswith(strip_prefix):
                if replacement_prefix is not None:
                    return "." + replacement_prefix + typename[len(strip_prefix):]
                else:
                    return typename[len(strip_prefix):]
            else:
                return typename

        if self.fdesc.package:
            if replacement_prefix is not None:
                base_name = Names(replacement_prefix)
            else:
                base_name = Names(self.fdesc.package.split('.'))
        else:
            base_name = Names()

        for enum in self.fdesc.enum_type:
            name = create_name(enum.name)
            enum_options = get_nanopb_suboptions(enum, self.file_options, name)
            self.enums.append(Enum(name, enum, enum_options))

        for names, message in iterate_messages(self.fdesc, flatten):
            name = create_name(names)
            message_options = get_nanopb_suboptions(message, self.file_options, name)

            if message_options.skip_message:
                continue

            message = copy.deepcopy(message)
            for field in message.field:
                if field.type in (FieldD.TYPE_MESSAGE, FieldD.TYPE_ENUM):
                    field.type_name = mangle_field_typename(field.type_name)

            self.messages.append(Message(name, message, message_options))
            for enum in message.enum_type:
                name = create_name(names + enum.name)
                enum_options = get_nanopb_suboptions(enum, message_options, name)
                self.enums.append(Enum(name, enum, enum_options))

        for names, extension in iterate_extensions(self.fdesc, flatten):
            name = create_name(names + extension.name)
            field_options = get_nanopb_suboptions(extension, self.file_options, name)
            if field_options.type != nanopb_pb2.FT_IGNORE:
                self.extensions.append(ExtensionField(name, extension, field_options))

    def add_dependency(self, other):
        for enum in other.enums:
            self.dependencies[str(enum.names)] = enum
            enum.protofile = other

        for msg in other.messages:
            self.dependencies[str(msg.name)] = msg
            msg.protofile = other

        # Fix field default values where enum short names are used.
        for enum in other.enums:
            if not enum.options.long_names:
                for message in self.messages:
                    for field in message.fields:
                        if field.default in enum.value_longnames:
                            idx = enum.value_longnames.index(field.default)
                            field.default = enum.values[idx][0]

        # Fix field data types where enums have negative values.
        for enum in other.enums:
            if not enum.has_negative():
                for message in self.messages:
                    for field in message.fields:
                        if field.pbtype == 'ENUM' and field.ctype == enum.names:
                            field.pbtype = 'UENUM'

    def generate_header(self, includes, headername, options):
        '''Generate content for a header file.
        Generates strings, which should be concatenated and stored to file.
        '''

        yield '/* Automatically generated nanopb header */\n'
        if options.notimestamp:
            yield '/* Generated by %s */\n\n' % (nanopb_version)
        else:
            yield '/* Generated by %s at %s. */\n\n' % (nanopb_version, time.asctime())

        if self.fdesc.package:
            symbol = make_identifier(self.fdesc.package + '_' + headername)
        else:
            symbol = make_identifier(headername)
        yield '#ifndef PB_%s_INCLUDED\n' % symbol
        yield '#define PB_%s_INCLUDED\n' % symbol
        try:
            yield options.libformat % ('pb.h')
        except TypeError:
            # no %s specified - use whatever was passed in as options.libformat
            yield options.libformat
        yield '\n'

        for incfile in includes:
            noext = os.path.splitext(incfile)[0]
            yield options.genformat % (noext + options.extension + options.header_extension)
            yield '\n'

        yield '/* @@protoc_insertion_point(includes) */\n'

        yield '#if PB_PROTO_HEADER_VERSION != 40\n'
        yield '#error Regenerate this file with the current version of nanopb generator.\n'
        yield '#endif\n'
        yield '\n'

        yield '#ifdef __cplusplus\n'
        yield 'extern "C" {\n'
        yield '#endif\n\n'

        if self.enums:
            yield '/* Enum definitions */\n'
            for enum in self.enums:
                yield str(enum) + '\n\n'

        if self.messages:
            yield '/* Struct definitions */\n'
            for msg in sort_dependencies(self.messages):
                yield msg.types()
                yield str(msg) + '\n\n'

        if self.extensions:
            yield '/* Extensions */\n'
            for extension in self.extensions:
                yield extension.extension_decl()
            yield '\n'

        if self.messages:
            yield '/* Initializer values for message structs */\n'
            for msg in self.messages:
                identifier = '%s_init_default' % msg.name
                yield '#define %-40s %s\n' % (identifier, msg.get_initializer(False))
            for msg in self.messages:
                identifier = '%s_init_zero' % msg.name
                yield '#define %-40s %s\n' % (identifier, msg.get_initializer(True))
            yield '\n'

            yield '/* Field tags (for use in manual encoding/decoding) */\n'
            for msg in sort_dependencies(self.messages):
                for field in msg.fields:
                    yield field.tags()
            for extension in self.extensions:
                yield extension.tags()
            yield '\n'

            yield '/* Struct field encoding specification for nanopb */\n'
            for msg in self.messages:
                yield msg.fields_declaration(self.dependencies) + '\n'
            for msg in self.messages:
                yield 'extern const pb_msgdesc_t %s_msg;\n' % msg.name
            yield '\n'

            yield '/* Defines for backwards compatibility with code written before nanopb-0.4.0 */\n'
            for msg in self.messages:
              yield '#define %s_fields &%s_msg\n' % (msg.name, msg.name)
            yield '\n'

            yield '/* Maximum encoded size of messages (where known) */\n'
            for msg in self.messages:
                msize = msg.encoded_size(self.dependencies)
                identifier = '%s_size' % msg.name
                if msize is not None:
                    yield '#define %-40s %s\n' % (identifier, msize)
                else:
                    yield '/* %s depends on runtime parameters */\n' % identifier
            yield '\n'

            if [msg for msg in self.messages if hasattr(msg,'msgid')]:
              yield '/* Message IDs (where set with "msgid" option) */\n'
              yield '#ifdef PB_MSGID\n'
              for msg in self.messages:
                  if hasattr(msg,'msgid'):
                      yield '#define PB_MSG_%d %s\n' % (msg.msgid, msg.name)
              yield '\n'

              symbol = make_identifier(headername.split('.')[0])
              yield '#define %s_MESSAGES \\\n' % symbol

              for msg in self.messages:
                  m = "-1"
                  msize = msg.encoded_size(self.dependencies)
                  if msize is not None:
                      m = msize
                  if hasattr(msg,'msgid'):
                      yield '\tPB_MSG(%d,%s,%s) \\\n' % (msg.msgid, m, msg.name)
              yield '\n'

              for msg in self.messages:
                  if hasattr(msg,'msgid'):
                      yield '#define %s_msgid %d\n' % (msg.name, msg.msgid)
              yield '\n'
              yield '#endif\n\n'

        yield '#ifdef __cplusplus\n'
        yield '} /* extern "C" */\n'
        yield '#endif\n'

        if options.cpp_descriptors:
            yield '\n'
            yield '#ifdef __cplusplus\n'
            yield '/* Message descriptors for nanopb */\n'
            yield 'namespace nanopb {\n'
            for msg in self.messages:
                yield msg.fields_declaration_cpp_lookup() + '\n'
            yield '}  // namespace nanopb\n'
            yield '\n'
            yield '#endif  /* __cplusplus */\n'
            yield '\n'

        # End of header
        yield '/* @@protoc_insertion_point(eof) */\n'
        yield '\n#endif\n'

    def generate_source(self, headername, options):
        '''Generate content for a source file.'''

        yield '/* Automatically generated nanopb constant definitions */\n'
        if options.notimestamp:
            yield '/* Generated by %s */\n\n' % (nanopb_version)
        else:
            yield '/* Generated by %s at %s. */\n\n' % (nanopb_version, time.asctime())
        yield options.genformat % (headername)
        yield '\n'
        yield '/* @@protoc_insertion_point(includes) */\n'

        yield '#if PB_PROTO_HEADER_VERSION != 40\n'
        yield '#error Regenerate this file with the current version of nanopb generator.\n'
        yield '#endif\n'
        yield '\n'

        for msg in self.messages:
            yield msg.fields_definition(self.dependencies) + '\n\n'

        for ext in self.extensions:
            yield ext.extension_def(self.dependencies) + '\n'

        for enum in self.enums:
            yield enum.enum_to_string_definition() + '\n'

        # Add checks for numeric limits
        if self.messages:
            largest_msg = max(self.messages, key = lambda m: m.count_required_fields())
            largest_count = largest_msg.count_required_fields()
            if largest_count > 64:
                yield '\n/* Check that missing required fields will be properly detected */\n'
                yield '#if PB_MAX_REQUIRED_FIELDS < %d\n' % largest_count
                yield '#error Properly detecting missing required fields in %s requires \\\n' % largest_msg.name
                yield '       setting PB_MAX_REQUIRED_FIELDS to %d or more.\n' % largest_count
                yield '#endif\n'

        # Add check for sizeof(double)
        has_double = False
        for msg in self.messages:
            for field in msg.fields:
                if field.ctype == 'double':
                    has_double = True

        if has_double:
            yield '\n'
            yield '/* On some platforms (such as AVR), double is really float.\n'
            yield ' * Using double on these platforms is not directly supported\n'
            yield ' * by nanopb, but see example_avr_double.\n'
            yield ' * To get rid of this error, remove any double fields from your .proto.\n'
            yield ' */\n'
            yield 'PB_STATIC_ASSERT(sizeof(double) == 8, DOUBLE_MUST_BE_8_BYTES)\n'

        yield '\n'
        yield '/* @@protoc_insertion_point(eof) */\n'

# ---------------------------------------------------------------------------
#                    Options parsing for the .proto files
# ---------------------------------------------------------------------------

from fnmatch import fnmatchcase

def read_options_file(infile):
    '''Parse a separate options file to list:
        [(namemask, options), ...]
    '''
    results = []
    data = infile.read()
    data = re.sub('/\*.*?\*/', '', data, flags = re.MULTILINE)
    data = re.sub('//.*?$', '', data, flags = re.MULTILINE)
    data = re.sub('#.*?$', '', data, flags = re.MULTILINE)
    for i, line in enumerate(data.split('\n')):
        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 1)

        if len(parts) < 2:
            sys.stderr.write("%s:%d: " % (infile.name, i + 1) +
                             "Option lines should have space between field name and options. " +
                             "Skipping line: '%s'\n" % line)
            continue

        opts = nanopb_pb2.NanoPBOptions()

        try:
            text_format.Merge(parts[1], opts)
        except Exception as e:
            sys.stderr.write("%s:%d: " % (infile.name, i + 1) +
                             "Unparseable option line: '%s'. " % line +
                             "Error: %s\n" % str(e))
            continue
        results.append((parts[0], opts))

    return results

class Globals:
    '''Ugly global variables, should find a good way to pass these.'''
    verbose_options = False
    separate_options = []
    matched_namemasks = set()

def get_nanopb_suboptions(subdesc, options, name):
    '''Get copy of options, and merge information from subdesc.'''
    new_options = nanopb_pb2.NanoPBOptions()
    new_options.CopyFrom(options)

    if hasattr(subdesc, 'syntax') and subdesc.syntax == "proto3":
        new_options.proto3 = True

    # Handle options defined in a separate file
    dotname = '.'.join(name.parts)
    for namemask, options in Globals.separate_options:
        if fnmatchcase(dotname, namemask):
            Globals.matched_namemasks.add(namemask)
            new_options.MergeFrom(options)

    # Handle options defined in .proto
    if isinstance(subdesc.options, descriptor.FieldOptions):
        ext_type = nanopb_pb2.nanopb
    elif isinstance(subdesc.options, descriptor.FileOptions):
        ext_type = nanopb_pb2.nanopb_fileopt
    elif isinstance(subdesc.options, descriptor.MessageOptions):
        ext_type = nanopb_pb2.nanopb_msgopt
    elif isinstance(subdesc.options, descriptor.EnumOptions):
        ext_type = nanopb_pb2.nanopb_enumopt
    else:
        raise Exception("Unknown options type")

    if subdesc.options.HasExtension(ext_type):
        ext = subdesc.options.Extensions[ext_type]
        new_options.MergeFrom(ext)

    if Globals.verbose_options:
        sys.stderr.write("Options for " + dotname + ": ")
        sys.stderr.write(text_format.MessageToString(new_options) + "\n")

    return new_options


# ---------------------------------------------------------------------------
#                         Command line interface
# ---------------------------------------------------------------------------

import sys
import os.path
from optparse import OptionParser

optparser = OptionParser(
    usage = "Usage: nanopb_generator.py [options] file.pb ...",
    epilog = "Compile file.pb from file.proto by: 'protoc -ofile.pb file.proto'. " +
             "Output will be written to file.pb.h and file.pb.c.")
optparser.add_option("-x", dest="exclude", metavar="FILE", action="append", default=[],
    help="Exclude file from generated #include list.")
optparser.add_option("-e", "--extension", dest="extension", metavar="EXTENSION", default=".pb",
    help="Set extension to use instead of '.pb' for generated files. [default: %default]")
optparser.add_option("-H", "--header-extension", dest="header_extension", metavar="EXTENSION", default=".h",
    help="Set extension to use for generated header files. [default: %default]")
optparser.add_option("-S", "--source-extension", dest="source_extension", metavar="EXTENSION", default=".c",
    help="Set extension to use for generated source files. [default: %default]")
optparser.add_option("-f", "--options-file", dest="options_file", metavar="FILE", default="%s.options",
    help="Set name of a separate generator options file.")
optparser.add_option("-I", "--options-path", dest="options_path", metavar="DIR",
    action="append", default = [],
    help="Search for .options files additionally in this path")
optparser.add_option("-D", "--output-dir", dest="output_dir",
                     metavar="OUTPUTDIR", default=None,
                     help="Output directory of .pb.h and .pb.c files")
optparser.add_option("-Q", "--generated-include-format", dest="genformat",
    metavar="FORMAT", default='#include "%s"\n',
    help="Set format string to use for including other .pb.h files. [default: %default]")
optparser.add_option("-L", "--library-include-format", dest="libformat",
    metavar="FORMAT", default='#include <%s>\n',
    help="Set format string to use for including the nanopb pb.h header. [default: %default]")

optparser.add_option("-F", "--file-format", dest="fileformat",
    metavar="FORMAT", default='%s',
    help="Set format string to use for the file base name. [default: %default]")

optparser.add_option("--strip-path", dest="strip_path", action="store_true", default=False,
    help="Strip directory path from #included .pb.h file name")
optparser.add_option("--no-strip-path", dest="strip_path", action="store_false",
    help="Opposite of --strip-path (default since 0.4.0)")
optparser.add_option("--cpp-descriptors", action="store_true",
    help="Generate C++ descriptors to lookup by type (e.g. pb_field_t for a message)")
optparser.add_option("-T", "--no-timestamp", dest="notimestamp", action="store_true", default=True,
    help="Don't add timestamp to .pb.h and .pb.c preambles (default since 0.4.0)")
optparser.add_option("-t", "--timestamp", dest="notimestamp", action="store_false", default=True,
    help="Add timestamp to .pb.h and .pb.c preambles")
optparser.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False,
    help="Don't print anything except errors.")
optparser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False,
    help="Print more information.")
optparser.add_option("-s", dest="settings", metavar="OPTION:VALUE", action="append", default=[],
    help="Set generator option (max_size, max_count etc.).")

def parse_file(filename, fdesc, options):
    '''Parse a single file. Returns a ProtoFile instance.'''
    toplevel_options = nanopb_pb2.NanoPBOptions()
    for s in options.settings:
        text_format.Merge(s, toplevel_options)

    if not fdesc:
        data = open(filename, 'rb').read()
        fdesc = descriptor.FileDescriptorSet.FromString(data).file[0]

    # Check if there is a separate .options file
    had_abspath = False
    try:
        optfilename = options.options_file % os.path.splitext(filename)[0]
    except TypeError:
        # No %s specified, use the filename as-is
        optfilename = options.options_file
        had_abspath = True

    paths = ['.'] + options.options_path
    for p in paths:
        if os.path.isfile(os.path.join(p, optfilename)):
            optfilename = os.path.join(p, optfilename)
            if options.verbose:
                sys.stderr.write('Reading options from ' + optfilename + '\n')
            Globals.separate_options = read_options_file(open(optfilename, "rU"))
            break
    else:
        # If we are given a full filename and it does not exist, give an error.
        # However, don't give error when we automatically look for .options file
        # with the same name as .proto.
        if options.verbose or had_abspath:
            sys.stderr.write('Options file not found: ' + optfilename + '\n')
        Globals.separate_options = []

    Globals.matched_namemasks = set()

    # Parse the file
    file_options = get_nanopb_suboptions(fdesc, toplevel_options, Names([filename]))
    f = ProtoFile(fdesc, file_options)
    f.optfilename = optfilename

    return f

def process_file(filename, fdesc, options, other_files = {}):
    '''Process a single file.
    filename: The full path to the .proto or .pb source file, as string.
    fdesc: The loaded FileDescriptorSet, or None to read from the input file.
    options: Command line options as they come from OptionsParser.

    Returns a dict:
        {'headername': Name of header file,
         'headerdata': Data for the .h header file,
         'sourcename': Name of the source code file,
         'sourcedata': Data for the .c source code file
        }
    '''
    f = parse_file(filename, fdesc, options)

    # Provide dependencies if available
    for dep in f.fdesc.dependency:
        if dep in other_files:
            f.add_dependency(other_files[dep])

    # Decide the file names
    noext = options.fileformat % os.path.splitext(filename)[0] \
                if '%s' in options.fileformat else options.fileformat 
    headername = noext + options.extension + options.header_extension
    sourcename = noext + options.extension + options.source_extension

    if options.strip_path:
        headerbasename = os.path.basename(headername)
    else:
        headerbasename = headername

    # List of .proto files that should not be included in the C header file
    # even if they are mentioned in the source .proto.
    excludes = ['nanopb.proto', 'google/protobuf/descriptor.proto'] + options.exclude
    includes = [d for d in f.fdesc.dependency if d not in excludes]

    if options.strip_path:
        includes = [os.path.basename(d) for d in includes]

    headerdata = ''.join(f.generate_header(includes, headerbasename, options))
    sourcedata = ''.join(f.generate_source(headerbasename, options))

    # Check if there were any lines in .options that did not match a member
    unmatched = [n for n,o in Globals.separate_options if n not in Globals.matched_namemasks]
    if unmatched and not options.quiet:
        sys.stderr.write("Following patterns in " + f.optfilename + " did not match any fields: "
                         + ', '.join(unmatched) + "\n")
        if not Globals.verbose_options:
            sys.stderr.write("Use  protoc --nanopb-out=-v:.   to see a list of the field names.\n")

    return {'headername': headername, 'headerdata': headerdata,
            'sourcename': sourcename, 'sourcedata': sourcedata}

def main_cli():
    '''Main function when invoked directly from the command line.'''

    options, filenames = optparser.parse_args()

    if not filenames:
        optparser.print_help()
        sys.exit(1)

    if options.quiet:
        options.verbose = False

    if options.output_dir and not os.path.exists(options.output_dir):
        optparser.print_help()
        sys.stderr.write("\noutput_dir does not exist: %s\n" % options.output_dir)
        sys.exit(1)

    if options.verbose:
        sys.stderr.write('Google Python protobuf library imported from %s, version %s\n'
                         % (google.protobuf.__file__, google.protobuf.__version__))

    Globals.verbose_options = options.verbose
    for filename in filenames:
        results = process_file(filename, None, options)

        base_dir = options.output_dir or ''
        to_write = [
            (os.path.join(base_dir, results['headername']), results['headerdata']),
            (os.path.join(base_dir, results['sourcename']), results['sourcedata']),
        ]

        if not options.quiet:
            paths = " and ".join([x[0] for x in to_write])
            sys.stderr.write("Writing to %s\n" % paths)

        for path, data in to_write:
            with open(path, 'w') as f:
                f.write(data)

def main_plugin():
    '''Main function when invoked as a protoc plugin.'''

    import io, sys
    if sys.platform == "win32":
        import os, msvcrt
        # Set stdin and stdout to binary mode
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    data = io.open(sys.stdin.fileno(), "rb").read()

    request = plugin_pb2.CodeGeneratorRequest.FromString(data)

    try:
        # Versions of Python prior to 2.7.3 do not support unicode
        # input to shlex.split(). Try to convert to str if possible.
        params = str(request.parameter)
    except UnicodeEncodeError:
        params = request.parameter

    import shlex
    args = shlex.split(params)

    if len(args) == 1 and ',' in args[0]:
        # For compatibility with other protoc plugins, support options
        # separated by comma.
        lex = shlex.shlex(params)
        lex.whitespace_split = True
        lex.whitespace = ','
        args = list(lex)

    optparser.usage = "Usage: protoc --nanopb_out=[options][,more_options]:outdir file.proto"
    optparser.epilog = "Output will be written to file.pb.h and file.pb.c."

    if '-h' in args or '--help' in args:
        # By default optparser prints help to stdout, which doesn't work for
        # protoc plugins.
        optparser.print_help(sys.stderr)
        sys.exit(1)

    options, dummy = optparser.parse_args(args)

    Globals.verbose_options = options.verbose

    if options.verbose:
        sys.stderr.write('Google Python protobuf library imported from %s, version %s\n'
                         % (google.protobuf.__file__, google.protobuf.__version__))

    response = plugin_pb2.CodeGeneratorResponse()

    # Google's protoc does not currently indicate the full path of proto files.
    # Instead always add the main file path to the search dirs, that works for
    # the common case.
    import os.path
    options.options_path.append(os.path.dirname(request.file_to_generate[0]))

    # Process any include files first, in order to have them
    # available as dependencies
    other_files = {}
    for fdesc in request.proto_file:
        other_files[fdesc.name] = parse_file(fdesc.name, fdesc, options)

    for filename in request.file_to_generate:
        for fdesc in request.proto_file:
            if fdesc.name == filename:
                results = process_file(filename, fdesc, options, other_files)

                f = response.file.add()
                f.name = results['headername']
                f.content = results['headerdata']

                f = response.file.add()
                f.name = results['sourcename']
                f.content = results['sourcedata']

    io.open(sys.stdout.fileno(), "wb").write(response.SerializeToString())

if __name__ == '__main__':
    # Check if we are running as a plugin under protoc
    if 'protoc-gen-' in sys.argv[0] or '--protoc-plugin' in sys.argv:
        main_plugin()
    else:
        main_cli()
