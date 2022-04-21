# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os.path
import platform
import re
import subprocess

from edalize.edatool import Edatool
from edalize.yosys import Yosys
from importlib import import_module

logger = logging.getLogger(__name__)

""" Generic backend

A core (usually the system core) can add the following files:

- Standard design sources (Verilog only)

- Constraints: unmanaged constraints with file_type SDC, pin_constraints with file_type PCF and placement constraints with file_type xdc

"""


class Generic(Edatool):

    argtypes = ["vlogdefine", "vlogparam", "generic"]
    archs = ["xilinx", "fpga_interchange"]
    fpga_interchange_families = ["xc7"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            symbiflow_help = {
                "members": [
                    {
                        "name" : "arch",
                        "type" : "String",
                        "desc" : "Target architecture. Legal values are *xilinx* and *fpga_interchange* (this is relevant only for Nextpnr variant)."
                    },
                    {
                        "name": "package",
                        "type": "String",
                        "desc": "FPGA chip package (e.g. clg400-1)",
                    },
                    {
                        "name": "part",
                        "type": "String",
                        "desc": "FPGA part type (e.g. xc7a50t)",
                    },
                    {
                        "name": "vendor",
                        "type": "String",
                        "desc": 'Target architecture. Currently only "xilinx" is supported',
                    },
                    {
                        "name": "pnr",
                        "type": "String",
                        "desc": 'Place and Route tool. Currently only "vpr"/"vtr" and "nextpnr" are supported',
                    },
                    {
                        "name": "vpr_options",
                        "type": "String",
                        "desc": "Additional options for VPR tool. If not used, default options for the tool will be used",
                    },
                    {
                        "name": "nextpnr_options",
                        "type": "String",
                        "desc": "Additional options for Nextpnr tool. If not used, default options for the tool will be used",
                    },
                    {
                        "name": "tool",
                        "type": "String",
                        "desc": "tool to run",
                    },
                    {
                        "name": "flags",
                        "type": "String",
                        "desc": "flags to be passed to the tool",
                    },
                    {
                        "name": "env_vars",
                        "type": "String",
                        "desc": "environment variables to be passed to the tool",
                    },
                    {
                        "name": "env_var_format",
                        "type": "String",
                        "desc": "format to be used with each environment variable",
                    },
                    {
                        "name": "vlog_catalog",
                        "type": "String",
                        "desc": "catalog of verilog files (one per line)",
                    },
                    {
                        "name": "vlog_format",
                        "type": "String",
                        "desc": "format to be used with each verilog file name",
                    },
                    {
                        "name": "svlog_catalog",
                        "type": "String",
                        "desc": "catalog of system verilog files (one per line)",
                    },
                    {
                        "name": "svlog_format",
                        "type": "String",
                        "desc": "format to be used with each system verilog file name",
                    },
                    {
                        "name": "tcl_format",
                        "type": "String",
                        "desc": "format to be used with each tcl file name",
                    },
                    {
                        "name": "incdir_catalog",
                        "type": "String",
                        "desc": "catalog of include directories (one per line)",
                    },
                    {
                        "name": "incdir_format",
                        "type": "String",
                        "desc": "format to be used with each include directory name",
                    },
                ],
            }

            symbiflow_members = symbiflow_help["members"]

            return {
                "description": "The Symbiflow backend executes Yosys sythesis tool and VPR/Nextpnr place and route. It can target multiple different FPGA vendors",
                "members": symbiflow_members,
            }

    def get_version(self):
        return "1.0"

    def configure_generic(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        verilog_file_list = []
        sverilog_file_list = []
        tcl_file_list = []
        include_dir_list = []
        env_var_list = []
        timing_constraints = []
        pins_constraints = []
        placement_constraints = []
        user_files = []
        
        if self.tool_options.get("vlog_format") == None:
            vlog_format = "{}"
        else:
            vlog_format = self.tool_options.get("vlog_format")
            
        if self.tool_options.get("svlog_format") == None:
            svlog_format = "{}"
        else:
            svlog_format = self.tool_options.get("svlog_format")
            
        if self.tool_options.get("tcl_format") == None:
            tcl_format = "{}"
        else:
            tcl_format = self.tool_options.get("tcl_format")
        
        for f in src_files:
            if f.file_type in ["verilogSource"]:
                verilog_file_list.append(vlog_format.format(f.name))
            if f.file_type in ["systemVerilogSource"]:
                sverilog_file_list.append(svlog_format.format(f.name))
            if f.file_type in ["tclSource"]:
                tcl_file_list.append(tcl_format.format(f.name))
            if f.file_type in ["SDC"]:
                timing_constraints.append(f.name)
            if f.file_type in ["PCF"]:
                pins_constraints.append(f.name)
            if f.file_type in ["xdc"]:
                placement_constraints.append(f.name)
            if f.file_type in ["user"]:
                user_files.append(f.name)
        
        if self.tool_options.get("vlog_catalog") == None:
            verilog_files = " ".join(verilog_file_list)
        else:
            verilog_files = ""
            file_path = os.path.join(self.work_root, self.tool_options.get("vlog_catalog"))
            with open(file_path, 'w') as file:
                for fname in verilog_file_list:
                    file.write(fname + '\n')
                file.close()
                
        if self.tool_options.get("svlog_catalog") == None:
            sverilog_files = " ".join(sverilog_file_list)
        else:
            sverilog_files = ""
            file_path = os.path.join(self.work_root, self.tool_options.get("svlog_catalog"))
            with open(file_path, 'w') as file:
                for fname in sverilog_file_list:
                    file.write(fname + '\n')
                file.close()
                
        tcl_files = " ".join(tcl_file_list)
        
        # Handle include directories       
        if self.tool_options.get("incdir_format") == None:
            incdir_format = "{}"
        else:
            incdir_format = self.tool_options.get("incdir_format")
            if self.tool_options.get("incdir_catalog") == None:
                for d in incdirs:
                    include_dir_list.append(incdir_format.format(d))
            else:
                file_path = os.path.join(self.work_root, self.tool_options.get("incdir_catalog"))
                with open(file_path, 'w') as file:
                    for d in incdirs:
                        text = incdir_format.format(d)
                        file.write(text + '\n')
                    file.close()

        part = self.tool_options.get("part")
        package = self.tool_options.get("package")
        vendor = self.tool_options.get("vendor")
        
        if self.tool_options.get("tool") == None:
            logger.error("tool was not specified -- generic needs to know which tool to run")
        else:
            tool = self.tool_options.get("tool")
        
        if self.tool_options.get("flags") == None:
            flags = ""
        else:
            flags = self.tool_options.get("flags")
        
        if self.tool_options.get("env_var_format") == None:
            env_var_format = "{}"
        else:
            env_var_format = self.tool_options.get("env_var_format")
            
        if self.tool_options.get("env_vars") == None:
            env_vars = ""
        else:
            env_vars = self.tool_options.get("env_vars").split()
            for env_var in env_vars:
                env_var_list.append(env_var_format.format(env_var))
            env_vars = " ".join(env_var_list)

        makefile_params = {
            "tool"              : tool,
            "flags"             : flags,
            "env_vars"          : env_vars,
            "verilog_files"     : verilog_files,
            "sverilog_files"    : sverilog_files,
            "tcl_files"         : tcl_files,
            "proj_dir"          : os.getcwd(),
            "inc_dirs"          : " ".join(include_dir_list),
            "sdc"               : " ".join(timing_constraints),
            "pcf"               : " ".join(pins_constraints),
            "xdc"               : " ".join(placement_constraints),
        }
        self.render_template("generic-makefile.j2", "Makefile", makefile_params)

    def configure_main(self):
        self.configure_generic()

    def run_main(self):
        logger.info("Programming")
