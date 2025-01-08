import os
import logging
import json
import sys

# print('##########')
# print(os.getcwd())
logging.basicConfig(level=logging.DEBUG,
                     filename='running.log',
                     format='%(asctime)s - %(levelname)s - %(message)s',
                     filemode='w')
# #logging.warning("1")
logger = logging.getLogger(__name__)
logger.debug("10")


file_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(file_dir, '..'))
sys.path.insert(0, os.getcwd())
import argparse

from ccscanner.utils.utils import read_txt, save_js
from ccscanner.extractors.conan_extractor import ConanExtractor
from ccscanner.extractors.control_extractor import ControlExtractor
from ccscanner.extractors.cmake_extractor import CmakeExtractor
from ccscanner.extractors.autoconf_extractor import AutoconfExtractor
from ccscanner.extractors.submodule_extractor import SubmodExtractor
from ccscanner.extractors.vcpkg_extractor import VcpkgExtractor
from ccscanner.extractors.pkg_extractor import PkgExtractor
from ccscanner.extractors.meson_extractor import MesonExtractor
from ccscanner.extractors.clib_extractor import ClibExtractor
from ccscanner.extractors.bazel_extractor import BazelExtractor
from ccscanner.extractors.ms_extractor import MsExtractor
from ccscanner.extractors.xmake_extractor import XmakeExtractor
from ccscanner.extractors.make_extractor import MakeExtractor
# from ccscanner.extractors.buckaroo_extractor import BuckarooExtractor
from ccscanner.extractors.dds_extractor import DdsExtractor
# from ccscanner.extractors.buck_extractor import BuckExtractor
from ccscanner.extractors.build2_extractor import Build2Extractor

parser = argparse.ArgumentParser()
parser.add_argument('-d', type=str, default='',
        help='set directory to scan')
parser.add_argument('-t', type=str, default='results.json',
        help='save results to file')

CONF_FILES = ['configure', 'configure.in', 'configure.ac']
# print('##########')
# print(os.getcwd())
logging.basicConfig(level=logging.DEBUG,
                    filename='running.log',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filemode='a')
#logging.warning("1")
logger = logging.getLogger(__name__)
logging.debug("20")
#logger.debug("2")
#logging.debug("1")


class scanner(object):
    def __init__(self, dir_target) -> None:
        self.target = dir_target
        self.extractors = []
        self.scan()

    def scan(self):
        for root, dirs, filenames in os.walk(self.target):
            for filename in filenames:
                extractor = None
                filename_lower = filename.lower()
                ## TODO: readme module
                # if filename_lower.startswith('readme'):
                #     extractor = ReadmeExtractor
                #     arg = os.path.join(root, filename)
                if filename_lower == 'control' or filename_lower.endswith('.dsc'):
                    extractor = ControlExtractor
                    arg = os.path.join(root, filename)
                elif filename == 'CMakeLists.txt' or filename.endswith('.cmake'):
                    extractor = CmakeExtractor
                    arg = os.path.join(root, filename)
                elif filename_lower in CONF_FILES:
                    extractor = AutoconfExtractor
                    arg = os.path.join(root, filename)
                elif filename == '.gitmodules':
                    extractor = SubmodExtractor
                    arg = root
                elif filename == 'vcpkg.json':
                    extractor = VcpkgExtractor
                    arg = os.path.join(root, filename)
                elif filename in ['conanfile.txt', 'conaninfo.txt', 'conanfile.py']:
                    extractor = ConanExtractor
                    arg = os.path.join(root, filename)
                elif filename.endswith('.pc'):
                    extractor = PkgExtractor
                    arg = os.path.join(root, filename)
                elif filename == 'meson.build':
                    extractor = MesonExtractor
                    arg = os.path.join(root, filename)
                elif filename in ['package.json', 'clib.json']:
                    extractor = ClibExtractor
                    arg = os.path.join(root, filename)
                elif filename == 'package.json5':
                    extractor = DdsExtractor
                    arg = os.path.join(root, filename)
                elif filename in ['bazel.build', 'BUILD']:
                    extractor = BazelExtractor
                    arg = os.path.join(root, filename)
                elif filename.endswith(('.vcxproj', '.vbproj', '.props')):
                    extractor = MsExtractor
                    arg = os.path.join(root, filename)
                elif filename == 'xmake.lua':
                    extractor = XmakeExtractor
                    arg = os.path.join(root, filename)
                ## elif filename in ['buckaroo.toml', 'buckaroo.lock.toml', '.buckconfig']:
                # elif filename in 'buckaroo.toml':
                #     extractor = BuckarooExtractor
                #     arg = os.path.join(root, filename)
                # elif filename == 'BUCK':
                #     extractor = BuckExtractor
                #     arg = os.path.join(root, filename)
                elif filename.lower().startswith('makefile'):
                    extractor = MakeExtractor
                    arg = os.path.join(root, filename)
                elif filename.lower() == 'manifest':
                    file_path = os.path.join(root, filename)
                    context = read_txt(file_path)
                    if 'build2' not in context:
                        continue
                    extractor = Build2Extractor
                    arg = file_path

                if extractor is None:
                    continue
                try:
                    extractor = extractor(arg)
                    extractor.run_extractor()
                    self.extractors.append(extractor.to_dict())
                except Exception as e:
                    logger.error("An error occurred:%s",str(e))

    def to_dict(self):
        return json.loads(json.dumps(self, default=lambda o: o.__dict__))


def main():
    args = parser.parse_args()
    target = args.d
    save_file = args.t
    logger.debug("test0")
    scanner_obj = scanner(target)
    res = scanner_obj.to_dict()
    save_js(res, save_file)
    logger.debug("3")


if __name__ == '__main__':
    main()
    # target = 'data/targets/projects/wireshark'
    # target = 'data/data_debian/salsa_repo_src/a11y-team@@at-spi2-atk'
    # target = 'tests/test_data'
    # res = test_scanner(target)
    # print(res)

    