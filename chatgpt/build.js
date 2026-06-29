import fs from 'node:fs';
import path from 'node:path';

// Create py directory
fs.mkdirSync('py', { recursive: true });

// Copy ../src to py/src
const srcDest = path.join('py', 'src');
if (fs.existsSync(srcDest)) {
  fs.rmSync(srcDest, { recursive: true, force: true });
}
fs.cpSync(path.join('..', 'src'), srcDest, { recursive: true });

// Copy ../pyproject.toml to py/pyproject.toml
fs.copyFileSync(path.join('..', 'pyproject.toml'), path.join('py', 'pyproject.toml'));

// Copy ../README.md to py/README.md
if (fs.existsSync(path.join('..', 'README.md'))) {
  fs.copyFileSync(path.join('..', 'README.md'), path.join('py', 'README.md'));
} else {
  fs.writeFileSync(path.join('py', 'README.md'), '# note-connector\n');
}

// Remove __pycache__ directories
function removePycache(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      if (file === '__pycache__') {
        fs.rmSync(fullPath, { recursive: true, force: true });
      } else {
        removePycache(fullPath);
      }
    }
  }
}
if (fs.existsSync(srcDest)) {
  removePycache(srcDest);
}

console.log("Python sources and README copied to py/ successfully.");
