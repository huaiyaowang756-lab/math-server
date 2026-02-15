# math-server

数学题目后台服务端，基于 Django + MongoDB。

## 环境依赖

- Python 3.10+
- MongoDB 6.0+（本地运行）
- ImageMagick 或 LibreOffice（WMF 转 PNG）
- pix2tex（可选，公式图转 LaTeX）

## 快速开始

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 确保 MongoDB 正在运行
brew services start mongodb-community
# 或
mongod --dbpath /data/db

# 3. 启动开发服务器
python manage.py runserver 8000
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/upload/ | 上传 docx 并解析 |
| POST | /api/questions/save/ | 保存题目到数据库 |
| GET | /api/questions/ | 获取题目列表（分页） |
| GET | /api/questions/:id/ | 获取单个题目 |
| PUT | /api/questions/:id/update/ | 更新题目 |
| DELETE | /api/questions/:id/delete/ | 删除题目 |
| DELETE | /api/questions/batch/ | 批量删除 |

## MongoDB 配置

默认连接 `localhost:27017`，数据库名 `math_questions`。

可在 `math_server/settings.py` 中修改：

```python
MONGO_DB_NAME = "math_questions"
MONGO_HOST = "localhost"
MONGO_PORT = 27017
```

## 解析流程（三阶段）

- **阶段一**：按原始 type 解析（text、wmf、png、jpeg 等），不做转换
- **阶段二**：WMF 公式 -> LaTeX；PNG/JPEG 等内容图 -> 保存到 TOS；text 不处理
- **阶段三**：返回结果，供前端确认保存

## TOS 对象存储配置

试题中的**内容图片**（如函数图象、题目附图，PNG/JPG 等）在阶段二上传到 TOS，文件名按内容 MD5 生成。**公式图**（WMF）转为 LaTeX 或 PNG 存本地 session。

1. 复制配置模板并填入桶的密钥：
   ```bash
   cp config/tos.yaml.example config/tos.yaml
   ```

2. 编辑 `config/tos.yaml`：
   - `enabled: true` 启用 TOS 上传
   - 填写 `endpoint_url`、`bucket`、`access_key_id`、`secret_access_key`
   - 填写 `public_base_url` 作为图片公开访问域名（或留空由 endpoint 拼接）

3. 支持 S3 兼容 API（火山引擎 TOS、腾讯 COS、阿里 OSS 等）
