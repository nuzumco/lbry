
"""Set the build version to be 'dev', 'qa', 'rc', 'release'"""

import os.path
import re
import subprocess
import sys


def main():
    build = get_build()
    root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    path = os.path.join(root_dir, 'lbrynet', 'build_type.py')
    print(f"Set build type: {path}", root_dir)
    with open(path, 'w') as f:
        f.write("BUILD = '{}'\n".format(build))


def get_build():
    try:
        tag = subprocess.check_output(['git', 'describe', '--exact-match', '--all']).strip()
        print(f"Tag info: {tag}")
        if re.match('tags\/v\d+\.\d+\.\d+rc\d+$', tag.decode()):
            print('Build: rc')
            return 'rc'
        elif re.match('tags\/v\d+\.\d+\.\d+$', tag.decode()):
            print('Build: release')
            return 'release'
        print('Build: qa')
        return 'qa'
    except subprocess.CalledProcessError:
        print("Couldn't determine build type, defaulting to qa.")
        return 'qa'
    except Exception as err:
        print(f"Failed to get tag info: {str(type(err))}({str(err)})")
        raise


if __name__ == '__main__':
    sys.exit(main())
