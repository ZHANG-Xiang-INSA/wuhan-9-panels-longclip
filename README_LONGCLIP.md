# 长卡扣优化分支

这是 `wuhan-9-panels` 的**完整副本**,用于卡扣系统优化。原目录 `../wuhan-9-panels/`
**一个字节都不动**,只读不写。

- 分支:`wuhan-9-panels-longclip`
- 基线:与原目录逐文件 MD5 相同的 200 个文件(见本目录第一个 commit)
- 目标:砖片的尺寸、数量、外观全部不变;只改卡扣系统

改什么、不改什么,见 `README.md` 里「导轨卡扣:按供应商的库存长度拼」一节。

## 与原目录的差异,逐条

| 项 | 原目录 | 本分支 |
|---|---|---|
| 砖片 | 1414 片 | **1414 片,逐个多边形相同** |
| 卡扣 | 1414 个,全 RC-50 加包边 | 1057 个:R1000 × 35、R700 × 92、R100 × 177、R50 × 703、包边 50 |
| 卡扣命名 | RC-50 | R50,与供应商图一致;整排用 R1000/R700/R100 |
| 板 9 | 154 个错开 R50 | **完全相同**(缝 3 mm 装不下整排导轨,见 `rails9.long_ok()`) |
| 板 3、5、6 | | 无连续段够长,不变 |
| R50 错开判据 | 缝 ≤ 3 才错开(只有板 9) | 缝 < 7 才错开(板 7、板 9) |
| 板 6 背板色 | `#edebeb`,采样偏中性 | `#ede6e5`,与板 4、5 一致的偏粉 |
| 放线图线色 | 砖 `#39332c` / 卡扣 `#1d5f86`,同明度难分 | 砖近黑 `#141414` / 卡扣蓝 `#0d6efd` / 孔红 `#d92b2b`;DXF 图层同步改为黑、蓝、红 |
| 砖类型 | 无 | L10 Yellow 用于板 1 至 3,L10 B2 用于板 4 至 6,L10 Grey 用于板 7 至 9;进 S7、S9、dxf/07、网站 |
| 备料 | 无 | +15%,按(型号 × 砖类型)逐项向上取整:砖 1633、卡扣 1221 |
| 汇总页 | 一张固定的表 | 分组按钮,砖按形状 / 砖类型 / 板号,卡扣按型号 / 砖类型 / 板号 |
| 下载 | 图纸、DXF、模型、PDF、JSON | 另加 `brick_schedule.csv`、`clip_schedule.csv` |

## 复核这一版时跑什么

```bash
python data/rails9.py           # 每种排长的拼法、逐板的导轨与 R50 数
python data/schedules_csv.py    # 写 CSV,并断言三种分组合计相等
python data/check_coverage.py   # 板面无重叠、无空档
python data/check_dxf.py dxf/06_clips_CN_EN.dxf dxf/08_setout_CN_EN.dxf
python data/check_all.py        # 持有量、明细与几何、备料算术、下载区与母本一致
python data/check_sheets.py     # S7/S8/S9 上的文字压线、压格、出血
```

网页打开后控制台若出现 `summary groupings disagree`,说明分组合计对不上,`assertGroups()`
会把三个数一起打出来。
