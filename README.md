# 姓名牌生成器

Windows 桌面工具：三处独立文字、字体与颜色，可调尺寸和字号，多盘 3MF 导出，每盘最多九块。

使用 Python 3.10，安装 requirements.txt 中的依赖，然后运行 app.py。现有工作区可使用“启动姓名牌生成器.cmd”。

打印配置：Bambu P2S、0.2 mm 喷嘴、PLA，四项填充图案为八角螺旋。

字体文件位于 assets/fonts 中，包含华康行楷体 W5-B5，拉取项目后无需另行安装该字体。华康字体来自用户提供的文件；开源字体的来源与许可文件保存在同目录。

详细功能记录见 README.txt。测试：python -m unittest discover -p test_generator.py。
