<!-- codex-memory:template=frontend-page-workflow:v1 -->

# Codex 前端页面固定流程

## 这份文档现在怎么用

它只规定一件事：

- Codex 在做页面时，应该按什么顺序推进

## 默认模式

先读：

- `.codex-memory/spec/frontend-design-standards.md`

然后根据自然语言需求继续完成：

- 理解页面目标
- 组织页面骨架
- 选择合适组件
- 落地实现
- 最后自检

## 固定执行顺序

1. 先读 `frontend-design-standards.md`
2. 先根据自然语言理解页面目标
3. 先输出本页定位
4. 先输出页面骨架
5. 再自己选 `shadcn/ui` 组件
6. 再开始实现页面
7. 最后按统一标准自检

## 固定底座

1. 组件统一从 `shadcn/ui` 来
2. 风格统一按项目规则和统一标准走
3. 如果需求没写清楚，不要自己发明新风格，先沿用现有规则
4. 如果项目本身不适合 `React / Next.js + Tailwind` 这条路线，就先明确说明，不能硬套

## 最后结论

稳定做法不是让用户先交一堆专业资料，而是：

- 用户继续用自然语言提需求
- Codex 自己先读统一标准
- Codex 自己在同一套组件和样式规则里完成页面
