const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, 'build');
const destDir = path.join(__dirname, '..', 'backend', 'static');

function deleteFolderRecursive(dirPath) {
  if (fs.existsSync(dirPath)) {
    fs.readdirSync(dirPath).forEach((file) => {
      const curPath = path.join(dirPath, file);
      if (fs.lstatSync(curPath).isDirectory()) {
        deleteFolderRecursive(curPath);
      } else {
        fs.unlinkSync(curPath);
      }
    });
    fs.rmdirSync(dirPath);
  }
}

function copyFolderRecursiveSync(source, target) {
  if (!fs.existsSync(target)) {
    fs.mkdirSync(target, { recursive: true });
  }

  if (fs.lstatSync(source).isDirectory()) {
    const files = fs.readdirSync(source);
    files.forEach((file) => {
      const curSource = path.join(source, file);
      const curTarget = path.join(target, file);
      if (fs.lstatSync(curSource).isDirectory()) {
        copyFolderRecursiveSync(curSource, curTarget);
      } else {
        fs.copyFileSync(curSource, curTarget);
      }
    });
  }
}

console.log('🧹 Cleaning backend/static directory...');
try {
  deleteFolderRecursive(destDir);
} catch (err) {
  console.warn('⚠️ Non-fatal error cleaning backend/static:', err.message);
}

console.log('🚀 Copying frontend build files to backend/static...');
try {
  copyFolderRecursiveSync(srcDir, destDir);
  console.log('✅ Successfully copied build files to backend/static!');
} catch (err) {
  console.warn('⚠️ Warning: Could not copy build files to backend/static (this is normal if building in a standalone frontend environment):', err.message);
}
