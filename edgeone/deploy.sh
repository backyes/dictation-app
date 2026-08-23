#!/bin/bash
# ============================================
# Tencent EdgeOne 部署脚本
# ============================================

set -e

echo "=========================================="
echo "  Tencent EdgeOne 部署脚本"
echo "=========================================="

# 配置
EDGEONE_DIR="./edgeone"
DIST_DIR="./dist"
FUNCTION_NAME="dictation-app"
REGION="ap-guangzhou"

# 1. 清理旧文件
echo ""
echo "[1/5] 清理旧文件..."
rm -rf $DIST_DIR
mkdir -p $DIST_DIR

# 2. 打包静态文件
echo ""
echo "[2/5] 打包静态文件..."
cp -r static $DIST_DIR/
cp -r templates $DIST_DIR/

# 3. 打包边缘函数
echo ""
echo "[3/5] 打包边缘函数..."
cp edgeone/function.js $DIST_DIR/

# 4. 安装依赖
echo ""
echo "[4/5] 安装依赖..."
cd $EDGEONE_DIR
if [ ! -f package.json ]; then
    cat > package.json << 'EOF'
{
  "name": "dictation-app-edgeone",
  "version": "1.0.0",
  "description": "英语听写练习 - EdgeOne 边缘函数",
  "main": "function.js",
  "type": "module"
}
EOF
fi
cd ..

# 5. 部署到 EdgeOne
echo ""
echo "[5/5] 部署到 EdgeOne..."
echo ""
echo "请确保已安装 EdgeOne CLI 并登录:"
echo "  npm install -g @tencent/edgeone-cli"
echo "  edgeone login"
echo ""
echo "部署命令:"
echo "  edgeone function create --name $FUNCTION_NAME --region $REGION"
echo "  edgeone function deploy --name $FUNCTION_NAME --source $DIST_DIR"
echo ""
echo "或者通过腾讯云控制台部署:"
echo "  1. 登录 https://console.cloud.tencent.com/edgeone"
echo "  2. 创建边缘函数"
echo "  3. 上传 $DIST_DIR/function.js"
echo "  4. 配置触发规则"
echo ""

echo "=========================================="
echo "部署准备完成！"
echo "=========================================="
echo ""
echo "部署文件位于: $DIST_DIR/"
echo ""
echo "后续步骤:"
echo "1. 将 Flask 后端部署到云服务器 (CVM) 或云函数 (SCF)"
echo "2. 配置 EdgeOne 环境变量:"
echo "   BACKEND_API=https://your-backend-domain.com"
echo "   STATIC_CDN=https://your-cdn-domain.com"
echo "3. 配置触发规则，将请求转发到边缘函数"
