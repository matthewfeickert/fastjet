#!/usr/bin/env python
# Copyright (c) 2021, Aryan Roy
#
# Distributed under the 3-clause BSD license, see accompanying file LICENSE
# or https://github.com/scikit-hep/fastjet for details.

from setuptools import setup  # isort:skip

# Available at setup time due to pyproject.toml
from pybind11.setup_helpers import Pybind11Extension  # isort:skip

import os
import pathlib
import platform
import shutil
import subprocess
import sys
import sysconfig

import setuptools.command.build_ext
import setuptools.command.install

DIR = pathlib.Path(__file__).parent.resolve()
FASTJET = DIR / "extern" / "fastjet-core"
FASTJET_CONTRIB = DIR / "extern" / "fastjet-contrib"
PYTHON = DIR / "src" / "fastjet"
OUTPUT = PYTHON / "_fastjet_core"


# Clean up transient directories to allow for rebuilds during development
if (DIR / "build").exists():
    shutil.rmtree(DIR / "build")
if OUTPUT.exists():
    shutil.rmtree(OUTPUT)

LIBS = [
    "fastjet",
    "fastjettools",
    "siscone",
    "siscone_spherical",
    "fastjetplugins",
    "fastjetcontribfragile",
]


def get_version() -> str:
    g = {}
    with open(PYTHON / "version.py") as f:
        exec(f.read(), g)
    return g["__version__"]


class FastJetBuild(setuptools.command.build_ext.build_ext):
    def build_extensions(self):
        if not OUTPUT.exists():
            # Patch for segfault of LimitedWarning
            # For more info see https://github.com/scikit-hep/fastjet/pull/131
            subprocess.run(
                ["patch", "src/ClusterSequence.cc", DIR / "patch_clustersequence.txt"],
                cwd=FASTJET,
            )

            # Hack to inject the required CXXFLAGS and LDFLAGS for building
            # on macOS aarch64 and with Conda.
            # This is a bad hack, and will be alleviated if CMake can be used
            # by FastJet and FastJet-contrib.
            # c.f. https://github.com/scikit-hep/fastjet/issues/310
            if (
                sys.platform == "darwin"
                and platform.processor() == "arm"
                and "HOMEBREW_PREFIX" in os.environ
            ):
                os.environ["CXXFLAGS"] = (
                    f"-I{os.environ['HOMEBREW_PREFIX']}/include "
                    + os.environ.get("CXXFLAGS", "")
                )
                os.environ["LDFLAGS"] = (
                    f"-L{os.environ['HOMEBREW_PREFIX']}/lib "
                    + os.environ.get("LDFLAGS", "")
                )
                # For reasons that are unclear, the LDFLAGS need to be fully
                # overridden. It is insufficient to just prepend the Homebrew
                # library path to the existing LDFLAGS.
                # os.environ["LDFLAGS"] = f"-L{os.environ['HOMEBREW_PREFIX']}/lib"
                # Pick up a Conda environment if it is active.
                # Note will still need coreutils and libtool installed with Homebrew.
                if "CONDA_PREFIX" in os.environ and os.environ["CONDA_PREFIX"]:
                    os.environ["CXXFLAGS"] = (
                        os.environ.get("CXXFLAGS", "")
                        + f" -I{os.environ['CONDA_PREFIX']}/include"
                    )

            # RPATH is set for shared libraries in the following locations:
            # * fastjet/
            # * fastjet/_fastjet_core/lib/
            # * fastjet/_fastjet_core/lib/python*/site-packages/
            _rpath = "'$$ORIGIN/_fastjet_core/lib:$$ORIGIN:$$ORIGIN/../..'"
            env = os.environ.copy()
            env["PYTHON"] = sys.executable
            env["PYTHON_INCLUDE"] = f'-I{sysconfig.get_path("include")}'
            env["CXXFLAGS"] = "-O3 -Bstatic -Bdynamic -std=c++17 " + env.get(
                "CXXFLAGS", ""
            )
            env["LDFLAGS"] = env.get("LDFLAGS", "") + f" -Wl,-rpath,{_rpath}"
            env["ORIGIN"] = "$ORIGIN"  # if evaluated, it will still be '$ORIGIN'

            args = [
                f"--prefix={OUTPUT}",
                "--enable-thread-safety",
                "--disable-auto-ptr",
                "--enable-allcxxplugins",
                "--enable-cgal-header-only",
                "--enable-cgal",
                "--enable-swig",
                "--enable-pyext",
                f'LDFLAGS={env["LDFLAGS"]}',
            ]

            try:
                subprocess.run(
                    ["./autogen.sh"] + args,
                    cwd=FASTJET,
                    env=env,
                    check=True,
                )
            except Exception:
                subprocess.run(["cat", "config.log"], cwd=FASTJET, check=True)
                raise

            env["ORIGIN"] = "$ORIGIN"  # if evaluated, it will still be '$ORIGIN'
            subprocess.run(["make", "-j"], cwd=FASTJET, env=env, check=True)
            subprocess.run(["make", "install"], cwd=FASTJET, env=env, check=True)

            # Update the environment for fastjet-contrib build
            env = os.environ.copy()
            env["CXX"] = env.get("CXX", "g++")
            env["LDFLAGS"] = env.get("LDFLAGS", "")

            # Hack to inject the required CXXFLAGS and LDFLAGS for building
            # on macOS aarch64 and with Conda.
            # For reasons that are unclear, the LDFLAGS need to be fully
            # overridden. It is insufficient to just prepend the Homebrew
            # library path to the existing LDFLAGS.
            # Things will _build_ without this, but then at runtime there
            # will be 'symbol not found in flat namespace' errors.
            # This is a bad hack, and will be alleviated if CMake can be used
            # by FastJet and FastJet-contrib.
            # c.f. https://github.com/scikit-hep/fastjet/issues/310
            #
            # Hm.....this WASN'T NEEDED IN CI!?!?! Only on local build with conda?
            #
            if (
                sys.platform == "darwin"
                and platform.processor() == "arm"
                and "HOMEBREW_PREFIX" in os.environ
            ):
                env["LDFLAGS"] = f"-L{env['HOMEBREW_PREFIX']}/lib"

            # For aarch64 macOS need to set the LDFLAGS for Homebrew installed
            # dependencies to be found. However, fastjet-contrib's configure
            # script does not use/accept LDFLAGS as an argument, and so to get
            # the library search path options passed to the linker it is necessary
            # to improperly inject them into the CXXFLAGS (which are used).
            # This is a bad hack, and will be alleviated if CMake can be used
            # by FastJet and FastJet-contrib.
            # c.f. https://github.com/scikit-hep/fastjet/issues/310
            subprocess.run(
                [
                    "./configure",
                    f"--fastjet-config={FASTJET}/fastjet-config",
                    f'CXX={env["CXX"]}',
                    f'CXXFLAGS=-O3 -Bstatic -Bdynamic -std=c++17{" "+env["LDFLAGS"] if sys.platform == "darwin" else ""}',
                ],
                cwd=FASTJET_CONTRIB,
                env=env,
                check=True,
            )
            subprocess.run(["make", "-j"], cwd=FASTJET_CONTRIB, env=env, check=True)
            subprocess.run(
                ["make", "install"], cwd=FASTJET_CONTRIB, env=env, check=True
            )
            subprocess.run(
                ["make", "fragile-shared"], cwd=FASTJET_CONTRIB, env=env, check=True
            )
            subprocess.run(
                ["make", "fragile-shared-install"],
                cwd=FASTJET_CONTRIB,
                env=env,
                check=True,
            )

        setuptools.command.build_ext.build_ext.build_extensions(self)


class FastJetInstall(setuptools.command.install.install):
    def run(self):
        fastjetdir = pathlib.Path(f"{self.build_lib}/fastjet")

        shutil.copytree(OUTPUT, fastjetdir / "_fastjet_core", symlinks=True)

        make = "gmake" if sys.platform == "darwin" else "make"
        pythondir = pathlib.Path(
            subprocess.check_output(
                f"""{make} -f Makefile --eval='print-pythondir:
\t@echo $(pythondir)
' print-pythondir""",
                shell=True,
                cwd=FASTJET / "pyinterface",
                universal_newlines=True,
            ).strip()
        )

        pyexecdir = pathlib.Path(
            subprocess.check_output(
                f"""{make} -f Makefile --eval='print-pyexecdir:
\t@echo $(pyexecdir)
' print-pyexecdir""",
                shell=True,
                cwd=FASTJET / "pyinterface",
                universal_newlines=True,
            ).strip()
        )

        shutil.copyfile(pythondir / "fastjet.py", fastjetdir / "_swig.py")
        shutil.copyfile(pyexecdir / "_fastjet.so", fastjetdir / "_fastjet.so")

        setuptools.command.install.install.run(self)


ext_modules = [
    Pybind11Extension(
        "fastjet._ext",
        ["src/_ext.cpp"],
        cxx_std=11,
        include_dirs=[str(OUTPUT / "include")],
        library_dirs=[str(OUTPUT / "lib")],
        runtime_library_dirs=["$ORIGIN/_fastjet_core/lib"],
        libraries=LIBS,
    ),
]


setup(
    version=get_version(),
    ext_modules=ext_modules,
    cmdclass={"build_ext": FastJetBuild, "install": FastJetInstall},
)
