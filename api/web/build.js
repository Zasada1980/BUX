const fs = require('fs');
const path = require('path');
const files = ['offline-shim.js', 'workday-report.js'];
const srcDir = path.join(__dirname, 'src');
const distDir = path.join(__dirname, 'dist');
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir);
}
files.forEach((name) => {
  const srcPath = path.join(srcDir, name);
  const distPath = path.join(distDir, name);
  const code = fs.readFileSync(srcPath, 'utf8');
  const bundled = code.trim() + '\n//# sourceMappingURL=' + name + '.map';
  fs.writeFileSync(distPath, bundled, 'utf8');
  const map = {
    version: 3,
    file: name,
    sources: [path.relative(distDir, srcPath)],
    names: [],
    mappings: ''
  };
  fs.writeFileSync(distPath + '.map', JSON.stringify(map), 'utf8');
});
console.log('Built bundles:', files.join(', '));
