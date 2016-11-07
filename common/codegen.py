#!/usr/bin/env python
#Generates communications code for the miniboard firmware, based on
#a command protocol specification document (see docparse.py) supplied
#as the first command-line argument.
#
#This code generation system has two goals: to allow commands to be easily added
#to the spec prior to their implementation, and to ensure that all commands
#function consistently. To accomplish this, all command-specific communication
#code is generated automatically from the specification document.
#For this to be possible, the code that actually carries out each command
#must be placed elsewhere. 
#
#Conceptually, commands to the rover read and write registers in its memory.
#This model makes separating communication and action easy. The automatically-generated
#communication code reads and writes fields in a large global struct (also automatically
#generated), with each field corresponding to a command argument.
#
#The output of this program is a source file and a header file containing the auto-generated
#communication code. 
#The global structure is called DataReal. Due to issues with the volatile qualifier
#(the main code needs it, but the ISR doesn't), the main code accesses DataReal through
#a pointer called Data.
#The parse_packet(uint8_t *buf, uint16_t count) function initiates packet
#parsing and dispatches the appropriate reply. buf must contain the command
#byte as the first byte in the buffer. count must be the number of bytes in
#the packet, not including the start or end bytes, and with escape bytes removed.
#
#The host program must provide a send_packet(uint8_t *data, uint16_t count) function
#which adds start/end bytes and escapes special characters, then sends the packet
#over the radio.
#The host program must also provide a memcpy() function.
#
#Additionally, there is an asynchronous command element beyond the simple read/write memory
#model. When a command includes a variable-length argument, a <command name>_trigger(uint8_t *data, uint16_t *len)
#function will be called when the command is received. This function must be implemented by
#the host code. The purpose of this mechanism is to notify the action code when the data
#changes. The trigger function must be capable of being run in an interrupt.
import sys
from docparse import *

def get_all_args(cmd_list):
	"""Return a list of tuples (format code, argument name, note comment)."""
	l = list()
	for c in cmd_list:
		for a in c["argument"]:
			l += [(a[0], a[1], c["notes"])]
	return l
	
def gen_struct_def(cmd_list):
	s = "struct comm_data_t {\n"
	for c in get_all_args(cmd_list):
		dt = format_code_to_cstdint(c[0])
		if "*" in dt:
			#Arrays
			s += "\t" + dt[0:-2] + " " + c[1] + "[%d];"%(2 ** int(dt[4:5])) + " /* " + c[2] + " */\n"
		else:
			s += "\t" + dt + " " + c[1] + ";" " /* " + c[2] + " */\n"
	s += "};\n\n"
	return s


def gen_header(cmd_list):
	"""Return a string containing the C header for the communication module."""
	s = "/* Warning: This file is automatically generated. Do not modify. */\n"
	s += "#ifndef COMMGEN_H\n"
	s += "#define COMMGEN_H\n\n"
	s += "#ifdef __cplusplus\n"
	s += "extern \"C\" {\n"
	s += "#endif\n\n"
	s += "#include <stdint.h>\n\n"
	s += gen_struct_def(cmd_list)
	s += "/* To avoid the volatile qualifier being a pain in the ass, the main loop\n"
	s += " * accesses the DataReal struct through this pointer. */\n"
	s += "extern volatile struct comm_data_t *Data;\n\n"
	s += "/* Parse a packet, update the struct, and send a reply. */\n"
	#s += "void parse_packet(uint8_t *buf, uint16_t count);\n\n"	
	for c in cmd_list:
		s += gen_send_proto(c) + "\n"
		s + gen_parse_proto(c) + "\n"
	s += gen_packing_protos()
	#s += "void send_packet(uint8_t *data, uint16_t count);\n\n"
	s += "#ifdef __cplusplus\n"
	s += "}\n"
	s += "#endif\n\n"	
	s += "#endif\n"
	return s
	
def gen_struct_dec(cmd_list):
	s = "struct comm_data_t DataReal = {\n"
	for c in cmd_list:
		for i,d in zip(range(0, len(c["default"])), c["default"]):
			s += "\t." + c["argument"][i][1] + " = " + d + ",\n"
	s += "};\n"
	s += "volatile struct comm_data_t *Data = &DataReal;\n"
	return s
	
def gen_source(cmd_list):
	s = "/* Warning: This file is automatically generated. Do not modify. */\n"
	s += "#include <stdint.h>\n"
	s += "#include <string.h>\n"
	s += "#include \"commgen.h\"\n\n"
	s += gen_struct_dec(cmd_list)
	for c in cmd_list:
		s += gen_parse_func(c) + "\n"
		s += gen_send_func(c, False) + "\n"
	s += gen_packing_funcs()
	s += gen_parse_packet_source(cmd_list)
	
	return s

def gen_parse_packet_source(cmd_list):
	#TODO: check for count == 0
	"""Return a string containing the source code to the 
	     parse_packet(uint8_t *buf, uint16_t count)
	   function, which parses a packet, updates values in the global Data structure,
	   and dispatches a reply.
	   The function relies on the following special functions:
	     send_packet(uint8_t *data, uint16_t count) - send the given packet across the radio link.
	                                                  The send_packet() function must add a start and end byte and 
	                                                  escape characters where necessary.
	   as well as the send_* and parse_* functions."""
	s = ""
	s += "void parse_packet(uint8_t *buf, uint16_t count){"
	s += "\tuint8_t cmd = buf[0];\n"
	s += "\tswitch(cmd){\n"
	for c in cmd_list:
		s += "\t\t/* %s */\n"%(c["name"])
		s += "\t\tcase 0x%02X: /* (Write form) */\n"%c["code"]
		s += "\t\t\tparse_%s(buf, "%cannon_name(c["name"])
		add_trigger = False
		for a in c["argument"]:
			if a[0] == "*":
				s += "DataReal.%s, "%(a[1])
				add_trigger = True;
			else:
				s += "&(DataReal.%s), "%(a[1])
		s = s[0:-2] + ");\n"
		s += "\t\t\tbuf[0] = cmd;\n"
		s += "\t\t\tsend_packet(buf, 1);\n"
		if add_trigger:
			s += "\t\t\t%s_trigger();\n"%cannon_name(c["name"])
		s += "\t\t\tbreak;\n"
		
		s += "\t\tcase 0x%02X: /* (Read form) */\n"%(c["code"] | 0x80)
		s += "\t\t\tsend_%s("%cannon_name(c["name"])
		for a in c["argument"]:
			s += "DataReal.%s, "%(a[1])
		s = s[0:-2] + ");\n"
		s += "\t\t\tbreak;\n"
	s += "\t\tdefault:\n"
	s += "\t\t\tbuf[0] = 0;\n"
	s += "\t\t\tsend_packet(buf, 1);\n"
	s += "\t\t\tbreak;\n"
	s += "\t}\n}\n"
	return s
	#TODO: writeable stuff 
		

def main():
	if len(sys.argv) != 4:
		sys.stderr.write("error: wrong number of arguments. Expected path to spec file, source file, and header file.")
	with open(sys.argv[1], "r") as f:
		cmds = extract_table(f.read())
		with open(sys.argv[3], "w") as f:
			f.write(gen_header(cmds))
		with open(sys.argv[2], "w") as f:
			f.write(gen_source(cmds))

if __name__ == "__main__":
	main()
	
