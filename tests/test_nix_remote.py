"""scripts/nix-remote.sh: HYPRUNE_BUILD_HOST from the environment, else ~/.config/hyprune/dev.env; never a default."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'scripts/nix-remote.sh').read_text()
# Only the host resolution: the lines from the dev.env lookup through HOST=.
RESOLVE = SCRIPT[SCRIPT.index('if [[ -z ${HYPRUNE_BUILD_HOST:-} ]]'):SCRIPT.index('\n', SCRIPT.index('HOST=${HYPRUNE_BUILD_HOST'))]


class BuildHost(unittest.TestCase):
    def resolve(self, dev_env=None, **env):
        with tempfile.TemporaryDirectory() as tmp:
            if dev_env is not None:
                (pathlib.Path(tmp) / 'hyprune').mkdir()
                (pathlib.Path(tmp) / 'hyprune/dev.env').write_text(dev_env)
            base = {k: v for k, v in os.environ.items() if k != 'HYPRUNE_BUILD_HOST'}
            return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + RESOLVE + '\necho "$HOST"'],
                                  env={**base, 'XDG_CONFIG_HOME': tmp, **env}, capture_output=True, text=True)

    def test_required(self):
        result = self.resolve()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('set HYPRUNE_BUILD_HOST', result.stderr)

    def test_dev_env_then_environment(self):
        self.assertEqual(self.resolve('# hosts\nexport HYPRUNE_BUILD_HOST="box.example"\n').stdout.strip(), 'box.example')
        self.assertEqual(self.resolve('HYPRUNE_BUILD_HOST=box.example\n', HYPRUNE_BUILD_HOST='env.example').stdout.strip(),
                         'env.example')


if __name__ == '__main__':
    unittest.main()
