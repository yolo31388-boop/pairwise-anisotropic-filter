# pairwise-anisotropic-filter

地面纹理在斜视角下远处糊成一片，UV 导数在三角形边界跳变，mip 选择按最大轴算导致纵向细节全丢；各向异性采样数固定 4，斜率达到 16:1 时出现一条条清晰带；三线性过滤在 mip 边界混合过宽，路面标线出现重影；负 LOD 偏置把近处纹理拉到远处 mip，细节被提前抹平；纹理数组层索引在 aniso 采样时没带 layer，相邻材质串色；BC7 压缩块的非均匀 alpha 被当成人不透明，栅栏边缘出现黑边；sampler 状态在材质切换后没重置，上一材质的 wrap 模式污染新材质；多相机分屏共用 sampler，左右眼各向异性方向不同却用同一组采样；UI 纹理被世界纹理的 aniso 设置影响，文字变糊；性能档降级直接把 aniso 关掉，斜视角突然变成硬边。render/anisotropic_filtering.py 是核心，tests/test_anisotropic_filtering.py 15个红。要修的是：UV 导数按像素 quad 重算；mip 按长轴与短轴比选；采样数随比率自适应；三线性按 mip 权重收紧；负 LOD 钳制；数组层随采样传递；BC7 alpha 模式按块读；sampler 状态按材质隔离；多相机独立采样方向；降级保留 2x aniso。

## 运行

```bash
python -m pytest tests -q
```

初始状态：15 个用例失败。修复实现使全部用例通过，不要修改 `tests/` 下的测试。

子方向：见平台；任务类型：Bugfix；语言/框架：Python 3, pytest；环境可复现等级：无外部依赖。
