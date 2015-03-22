#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys, os, xpidl

from mozbuild.makeutil import write_dep_makefile
from mozbuild.util import FileAvoidWrite

def findIDL(includePath, interfaceFileName):
    for d in includePath:
        # Not os.path.join: we need a forward slash even on Windows because
        # this filename ends up in makedepend output.
        path = d + '/' + interfaceFileName
        if os.path.exists(path):
            return path
    raise BaseException("No IDL file found for interface %s "
                        "in include path %r"
                        % (interfaceFileName, includePath))

def loadEventIDL(parser, includePath, eventname):
    eventidl = ("nsIAccessible%s.idl" % eventname)
    idlFile = findIDL(includePath, eventidl)
    idl = p.parse(open(idlFile).read(), idlFile)
    idl.resolve(includePath, p)
    return idl, idlFile

class Configuration:
    def __init__(self, filename):
        config = {}
        execfile(filename, config)
        self.simple_events = config.get('simple_events', [])

def readConfigFile(filename):
    return Configuration(filename)

def firstCap(str):
    return str[0].upper() + str[1:]

def writeAttributeParams(a):
    return ("%s a%s" % (a.realtype.nativeType('in'), firstCap(a.name)))

def print_header_file(fd, conf):
    idl_paths = set()

    fd.write("/* THIS FILE IS AUTOGENERATED - DO NOT EDIT */\n")
    fd.write("#ifndef _mozilla_a11y_generated_AccEvents_h_\n"
             "#define _mozilla_a11y_generated_AccEvents_h_\n\n")
    fd.write("#include \"nscore.h\"\n")
    fd.write("#include \"nsCOMPtr.h\"\n")
    fd.write("#include \"nsCycleCollectionParticipant.h\"\n")
    fd.write("#include \"nsString.h\"\n")
    for e in conf.simple_events:
        fd.write("#include \"nsIAccessible%s.h\"\n" % e)
    for e in conf.simple_events:
        idl, idl_path = loadEventIDL(p, options.incdirs, e)
        idl_paths.add(idl_path)
        for iface in filter(lambda p: p.kind == "interface", idl.productions):
            classname = ("xpcAcc%s" % e)
            baseinterfaces = interfaces(iface)

            fd.write("\nclass %s MOZ_FINAL : public %s\n" % (classname, iface.name))
            fd.write("{\n")
            fd.write("public:\n")

            attributes = allAttributes(iface)
            args = map(writeAttributeParams, attributes)
            fd.write("  %s(%s) :\n" % (classname, ", ".join(args)))

            initializers = []
            for a in attributes:
                initializers.append("m%s(a%s)" % (firstCap(a.name), firstCap(a.name)))
            fd.write("  %s\n  {}\n\n" % ", ".join(initializers))
            fd.write("  NS_DECL_CYCLE_COLLECTING_ISUPPORTS\n")
            fd.write("  NS_DECL_CYCLE_COLLECTION_CLASS(%s)\n" % (classname))

            for iface in filter(lambda i: i.name != "nsISupports", baseinterfaces):
                fd.write("  NS_DECL_%s\n" % iface.name.upper())

            fd.write("\nprivate:\n")
            fd.write("  ~%s() {}\n\n" % classname)
            for a in attributes:
                fd.write("  %s\n" % attributeVariableTypeAndName(a))
            fd.write("};\n\n")

    fd.write("#endif\n")

    return idl_paths

def interfaceAttributeTypes(idl):
    ifaces = filter(lambda p: p.kind == "interface", idl.productions)
    attributes = []
    for i in ifaces:
        ifaceAttributes = allAttributes(i)
        attributes.extend(ifaceAttributes)
    ifaceAttrs = filter(lambda a: a.realtype.nativeType("in").endswith("*"), attributes)
    return map(lambda a: a.realtype.nativeType("in").strip(" *"), ifaceAttrs)

def print_cpp(idl, fd, conf, eventname):
    for p in idl.productions:
        if p.kind == 'interface':
            write_cpp(eventname, p, fd)

def print_cpp_file(fd, conf):
    idl_paths = set()
    fd.write("/* THIS FILE IS AUTOGENERATED - DO NOT EDIT */\n\n")
    fd.write('#include "xpcAccEvents.h"\n')

    includes = []
    for e in conf.simple_events:
        if not e in includes:
            includes.append(("nsIAccessible%s" % e))

    types = []
    for e in conf.simple_events:
        idl, idl_path = loadEventIDL(p, options.incdirs, e)
        idl_paths.add(idl_path)
        types.extend(interfaceAttributeTypes(idl))

    for c in types:
        fd.write("#include \"%s.h\"\n" % c)

    fd.write("\n")
    for e in conf.simple_events:
        idl, idl_path = loadEventIDL(p, options.incdirs, e)
        idl_paths.add(idl_path)
        print_cpp(idl, fd, conf, e)

    return idl_paths

def attributeVariableTypeAndName(a):
    if a.realtype.nativeType('in').endswith('*'):
        l = ["nsCOMPtr<%s> m%s;" % (a.realtype.nativeType('in').strip('* '),
                   firstCap(a.name))]
    elif a.realtype.nativeType('in').count("nsAString"):
        l = ["nsString m%s;" % firstCap(a.name)]
    elif a.realtype.nativeType('in').count("nsACString"):
        l = ["nsCString m%s;" % firstCap(a.name)]
    else:
        l = ["%sm%s;" % (a.realtype.nativeType('in'),
                       firstCap(a.name))]
    return ", ".join(l)

def writeAttributeGetter(fd, classname, a):
    fd.write("NS_IMETHODIMP\n")
    fd.write("%s::Get%s(" % (classname, firstCap(a.name)))
    if a.realtype.nativeType('in').endswith('*'):
        fd.write("%s** a%s" % (a.realtype.nativeType('in').strip('* '), firstCap(a.name)))
    elif a.realtype.nativeType('in').count("nsAString"):
        fd.write("nsAString& a%s" % firstCap(a.name))
    elif a.realtype.nativeType('in').count("nsACString"):
        fd.write("nsACString& a%s" % firstCap(a.name))
    else:
        fd.write("%s*a%s" % (a.realtype.nativeType('in'), firstCap(a.name)))
    fd.write(")\n");
    fd.write("{\n");
    if a.realtype.nativeType('in').endswith('*'):
        fd.write("  NS_IF_ADDREF(*a%s = m%s);\n" % (firstCap(a.name), firstCap(a.name)))
    elif a.realtype.nativeType('in').count("nsAString"):
        fd.write("  a%s = m%s;\n" % (firstCap(a.name), firstCap(a.name)))
    elif a.realtype.nativeType('in').count("nsACString"):
        fd.write("  a%s = m%s;\n" % (firstCap(a.name), firstCap(a.name)))
    else:
        fd.write("  *a%s = m%s;\n" % (firstCap(a.name), firstCap(a.name)))
    fd.write("  return NS_OK;\n");
    fd.write("}\n\n");

def interfaces(iface):
    interfaces = []
    while iface.base:
        interfaces.append(iface)
        iface = iface.idl.getName(iface.base, iface.location)
    interfaces.append(iface)
    interfaces.reverse()
    return interfaces

def allAttributes(iface):
    attributes = []
    for i in interfaces(iface):
        attrs = filter(lambda m: isinstance(m, xpidl.Attribute), i.members)
        attributes.extend(attrs)

    return attributes

def write_cpp(eventname, iface, fd):
    classname = "xpcAcc%s" % eventname
    attributes = allAttributes(iface)
    ccattributes = filter(lambda m: m.realtype.nativeType('in').endswith('*'), attributes)
    fd.write("NS_IMPL_CYCLE_COLLECTION(%s" % classname)
    for c in ccattributes:
        fd.write(", m%s" % firstCap(c.name))
    fd.write(")\n\n");

    fd.write("NS_IMPL_CYCLE_COLLECTING_ADDREF(%s)\n" % classname)
    fd.write("NS_IMPL_CYCLE_COLLECTING_RELEASE(%s)\n\n" % classname)

    fd.write("NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(%s)\n" % classname)
    for baseiface in interfaces(iface):
        fd.write("  NS_INTERFACE_MAP_ENTRY(%s)\n" % baseiface.name)
    fd.write("NS_INTERFACE_MAP_END\n\n")

    for a in attributes:
        writeAttributeGetter(fd, classname, a)


def main():
    from argparse import ArgumentParser
    o = ArgumentParser()
    o.add_argument('-I', action='append', dest='incdirs', default=['.'],
                 help="Directory to search for imported files")
    o.add_argument('config',
                 help='Config file to load')
    o.add_argument('header_output', metavar='FILE',
                 help="Quick stub header output file")
    o.add_argument('stub_output', metavar='FILE',
                 help="C++ source output file")
    o.add_argument('makedepend_output', metavar='FILE',
                 help="gnumake dependencies output file")
    global options
    options = o.parse_args()

    # Instantiate the parser.
    global p
    p = xpidl.IDLParser()

    conf = readConfigFile(options.config)

    with FileAvoidWrite(options.header_output) as fh:
        idl_paths = print_header_file(fh, conf)
    with FileAvoidWrite(options.stub_output) as fh:
        idl_paths |= print_cpp_file(fh, conf)
    with FileAvoidWrite(options.makedepend_output) as fh:
        write_dep_makefile(fh, options.stub_output, idl_paths)

if __name__ == '__main__':
    main()