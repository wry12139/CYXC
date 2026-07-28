# 王仁懿 - 个人在线简历 v2

现代化、交互式个人简历网站。深色配色 + Three.js 3D 背景 + GSAP 动画 + 三层视差滚动，提供沉浸式浏览体验。

## 在线访问

- **v2（最新）**：http://14.103.185.222:8006/external/rowan/personal-intro-v2/
- **v1**：http://14.103.185.222:8006/external/rowan/personal-intro/

## 主要特性

- **3D 背景**：三个 section 各有独立的 Three.js 粒子/几何体场景
- **GSAP 动画**：加载动画、卡片悬停、滚动触发、视差
- **交互增强**：鼠标跟踪、3D 卡片倾斜、技能条动画、发光效果
- **响应式**：768px 移动断点，1024px 平板断点
- **无障碍**：语义化标签 + 键盘可用

## 页面结构

1. **个人介绍** — 名字展示、身份、简介、快速导航
2. **技能 & 爱好** — 编程语言、Web 开发、技术探索、篮球、FPS、肉鸽
3. **项目 & 联系** — 三个项目卡片、邮箱、飞书

## 技术栈

| 类别 | 技术 |
|---|---|
| 结构 | HTML5 |
| 样式 | CSS3 + Tailwind CSS |
| 3D | Three.js r128 |
| 动画 | GSAP 3.12.2（ScrollTrigger + ScrollToPlugin） |
| 平滑滚动 | Lenis 1.0.29 |
| 字体 | Geist、Outfit（Google Fonts） |

## 项目结构

```
personal-intro.html          # 主入口（HTML + CSS + 模块导入）
js/
├── three-bg.js              # Three.js 3D 背景系统
├── gsap-animations.js       # 加载/悬停/滚动/视差动画
├── interactive.js           # 平滑滚动、返回顶部、响应式、无障碍
└── interactive-enhanced.js  # 鼠标跟踪、3D 倾斜、技能条、发光
```

模块通过 ES6 `import`/`export` 加载。

## 本地运行

由于使用 ES6 模块，需要通过 HTTP 服务器打开：

```bash
# Python
python -m http.server 8000

# Node
npx serve .
```

然后访问 http://localhost:8000/personal-intro.html

## 联系方式

- 邮箱：w3548191285@163.com
- 飞书：@王仁懿

---

**作者**：王仁懿 · 西北工业大学（NPU）
