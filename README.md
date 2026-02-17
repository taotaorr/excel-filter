# Excel文件上传与筛选系统

这是一个运行在阿里云服务器上的Web应用，提供Excel文件上传和字段筛选功能。

## 功能特点
- 支持上传Excel文件(.xlsx, .xls)
- 自动识别Excel中的所有字段
- 支持多条件筛选
- 支持数据导出

## 技术栈
- 后端：Flask + pandas + openpyxl
- 前端：HTML5 + JavaScript + Bootstrap

## 本地运行
```bash
pip install flask pandas openpyxl
python app.py
```
访问 http://localhost:5000

## 阿里云部署
详见 DEPLOY.md
