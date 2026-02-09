"""
爆款拆解模块 - 分析高表现内容的成功模式

功能：
1. 拆解爆款内容的标题、结构、情感
2. 提取可复用的成功模式
3. 生成内容创作建议
4. 标签和话题分析
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
from core.analytics import ContentAnalytics
from core.title_optimizer import TitleOptimizer


class ViralAnalyzer:
    """爆款内容拆解器"""

    def __init__(self, recorder, analytics=None):
        self.recorder = recorder
        self.analytics = analytics or ContentAnalytics(recorder)
        self.title_optimizer = TitleOptimizer(recorder)

        # 成功模式模板库
        self.pattern_templates = {
            "工具推荐": {
                "结构": "痛点场景 → 工具介绍 → 使用效果 → 总结推荐",
                "标题特征": ["数字型", "神器", "必备", "效率提升"],
                "关键词": ["神器", "必备", "神器", "救我", "相见恨晚"],
                "情感基调": "热情推荐、解决痛点"
            },
            "教程分享": {
                "结构": "问题引入 → 步骤演示 → 效果展示 → 注意事项",
                "标题特征": ["保姆级", "手把手", "教程", "从入门到精通"],
                "关键词": ["保姆级", "手把手", "教程", "攻略"],
                "情感基调": "耐心教导、实用干货"
            },
            "避坑指南": {
                "结构": "踩坑经历 → 问题分析 → 解决方案 → 避坑建议",
                "标题特征": ["避坑", "别再", "不要", "错误"],
                "关键词": ["避坑", "别再", "不要", "千万别"],
                "情感基调": "真诚提醒、经验分享"
            },
            "合集推荐": {
                "结构": "需求引入 → 多个工具推荐 → 适用场景 → 取用建议",
                "标题特征": ["合集", "盘点", "推荐", "精选"],
                "关键词": ["合集", "盘点", "推荐", "精选", "必看"],
                "情感基调": "丰富全面、按需取用"
            },
            "测评对比": {
                "结构": "对比背景 → 多维度对比 → 优缺点分析 → 选择建议",
                "标题特征": ["对比", "测评", "VS", "哪个好"],
                "关键词": ["对比", "测评", "VS", "哪个好", "区别"],
                "情感基调": "客观分析、真实体验"
            }
        }

    def analyze_viral_content(self, draft: Dict, stats: Dict) -> Dict:
        """
        深度拆解单个爆款内容

        Args:
            draft: 草稿数据
            stats: 统计数据

        Returns:
            拆解结果字典
        """
        title = draft.get("title", "")
        content = draft.get("content", "")
        tags = draft.get("tags", [])
        style = draft.get("style", "")

        # 计算内容表现评分
        score = self.analytics.calculate_score(stats)

        analysis = {
            "draft_id": draft.get("created_at", ""),
            "title": title,
            "score": score,
            "stats": stats,
            "patterns": {}
        }

        # 1. 标题分析
        title_analysis = self._analyze_title(title)
        analysis["patterns"]["title"] = title_analysis

        # 2. 内容结构分析
        content_structure = self._analyze_content_structure(content)
        analysis["patterns"]["content_structure"] = content_structure

        # 3. 情感分析
        emotion_analysis = self._analyze_emotion(content)
        analysis["patterns"]["emotion"] = emotion_analysis

        # 4. 标签分析
        tag_analysis = self._analyze_tags(tags)
        analysis["patterns"]["tags"] = tag_analysis

        # 5. 视觉分析（如果有图片提示词）
        image_prompt = draft.get("image_prompt", "")
        if image_prompt:
            visual_analysis = self._analyze_visual(image_prompt)
            analysis["patterns"]["visual"] = visual_analysis

        # 6. 成功要素总结
        success_factors = self._extract_success_factors(analysis)
        analysis["success_factors"] = success_factors

        return analysis

    def _analyze_title(self, title: str) -> Dict:
        """分析标题特征"""
        # 标题评分
        title_score = self.title_optimizer._calculate_score(title)

        # 提取特征
        features = {
            "length": len(title),
            "score": title_score,
            "has_number": bool(re.search(r'\d+', title)),
            "has_emoji": bool(re.search(r'[^\w\s]', title)),
            "type": self._classify_title_type(title),
            "keywords": self._extract_title_keywords(title)
        }

        return features

    def _classify_title_type(self, title: str) -> str:
        """分类标题类型"""
        if re.search(r'\d+[个款项]', title):
            return "数字型"
        elif re.search(r'[?？]', title):
            return "疑问型"
        elif re.search(r'(VS|vs|对比|区别)', title):
            return "对比型"
        elif re.search(r'(避坑|别再|不要|千万别)', title):
            return "痛点型"
        elif re.search(r'(保姆级|手把手|教程|攻略)', title):
            return "干货型"
        elif re.search(r'(绝了|太香|相见恨晚|真香)', title):
            return "情感型"
        else:
            return "普通型"

    def _extract_title_keywords(self, title: str) -> List[str]:
        """提取标题关键词"""
        # 情感词汇
        emotional_words = ["神器", "必备", "绝了", "太香", "相见恨晚", "真香",
                          "救命", "起飞", "翻倍", "轻松", "搞定", "解放"]

        keywords = []
        for word in emotional_words:
            if word in title:
                keywords.append(word)

        return keywords

    def _analyze_content_structure(self, content: str) -> Dict:
        """分析内容结构"""
        paragraphs = content.split('\n')
        non_empty_para = [p.strip() for p in paragraphs if p.strip()]

        structure = {
            "paragraph_count": len(non_empty_para),
            "total_length": len(content),
            "avg_paragraph_length": len(content) // max(len(non_empty_para), 1),
            "opening_type": self._classify_opening(non_empty_para[0] if non_empty_para else ""),
            "has_call_to_action": self._check_call_to_action(content),
            "scene_based": self._check_scene_based(content)
        }

        return structure

    def _classify_opening(self, opening: str) -> str:
        """分类开头类型"""
        if re.search(r'(深夜|加班|赶稿|面对堆积)', opening):
            return "场景切入"
        elif re.search(r'(被问爆|最近|终于)', opening):
            return "时间引入"
        elif re.search(r'(今天|分享|推荐)', opening):
            return "直入主题"
        elif re.search(r'(你知道吗|有没有|是不是)', opening):
            return "疑问引入"
        else:
            return "其他"

    def _check_call_to_action(self, content: str) -> bool:
        """检查是否有行动召唤"""
        cta_patterns = [
            r'试试', r'关注', r'点赞', r'收藏', r'评论',
            r'试试看', r'记得', r'别忘了'
        ]
        return any(re.search(pattern, content) for pattern in cta_patterns)

    def _check_scene_based(self, content: str) -> bool:
        """检查是否是场景化内容"""
        scene_patterns = [
            r'深夜', r'加班', r'赶稿', r'月底', r'总结',
            r'同事', r'老板', r'任务', r'项目'
        ]
        return any(re.search(pattern, content) for pattern in scene_patterns)

    def _analyze_emotion(self, content: str) -> Dict:
        """分析情感特征"""
        # 痛点词汇
        pain_points = ["折磨", "崩溃", "头秃", "抓狂", "焦虑", "痛苦", "烦"]
        # 解决词汇
        solutions = ["救命", "绝了", "太香", "相见恨晚", "真香", "好用到哭"]
        # 效果词汇
        effects = ["起飞", "翻倍", "轻松", "搞定", "解放", "提升", "效率"]

        pain_count = sum(1 for word in pain_points if word in content)
        solution_count = sum(1 for word in solutions if word in content)
        effect_count = sum(1 for word in effects if word in content)

        return {
            "pain_point_score": pain_count,
            "solution_score": solution_count,
            "effect_score": effect_count,
            "total_emotional_score": pain_count + solution_count + effect_count,
            "emotion_type": self._classify_emotion_type(pain_count, solution_count, effect_count)
        }

    def _classify_emotion_type(self, pain: int, solution: int, effect: int) -> str:
        """分类情感类型"""
        if pain > 0 and solution > 0:
            return "痛点-解决型"
        elif effect > 0:
            return "效果强调型"
        elif solution > 0:
            return "推荐型"
        else:
            return "平实型"

    def _analyze_tags(self, tags: List[str]) -> Dict:
        """分析标签特征"""
        return {
            "tag_count": len(tags),
            "tags": tags,
            "has_ai_tag": any("AI" in tag for tag in tags),
            "has_tool_tag": any("工具" in tag for tag in tags),
            "has_efficiency_tag": any("效率" in tag for tag in tags)
        }

    def _analyze_visual(self, image_prompt: str) -> Dict:
        """分析视觉特征"""
        visual_keywords = {
            "科技感": ["tech", "modern", "digital", "futuristic"],
            "简洁": ["clean", "minimal", "simple", "clear"],
            "蓝色": ["blue", "cyan", "navy"],
            "工具界面": ["interface", "UI", "screen", "workspace"]
        }

        found_features = []
        for feature, keywords in visual_keywords.items():
            if any(keyword.lower() in image_prompt.lower() for keyword in keywords):
                found_features.append(feature)

        return {
            "prompt_length": len(image_prompt),
            "visual_features": found_features,
            "has_style_keywords": len(found_features) > 0
        }

    def _extract_success_factors(self, analysis: Dict) -> List[str]:
        """提取成功要素"""
        factors = []

        # 基于评分
        if analysis["score"] >= 70:
            factors.append("📊 高互动率内容")

        # 基于标题
        title = analysis["patterns"]["title"]
        if title["score"] >= 60:
            factors.append(f"🎯 高分标题 ({title['type']})")
        if title["has_number"]:
            factors.append("🔢 数字化标题")
        if title["has_emoji"]:
            factors.append("😊 表情符号标题")

        # 基于内容结构
        content = analysis["patterns"]["content_structure"]
        if content["scene_based"]:
            factors.append("🎬 场景化内容")
        if content["has_call_to_action"]:
            factors.append("📢 包含行动召唤")

        # 基于情感
        emotion = analysis["patterns"]["emotion"]
        if emotion["total_emotional_score"] >= 3:
            factors.append(f"💭 情感化内容 ({emotion['emotion_type']})")

        # 基于标签
        tags = analysis["patterns"]["tags"]
        if tags["has_ai_tag"] and tags["has_tool_tag"]:
            factors.append("🏷️ 标签组合完整")

        return factors if factors else ["📝 基础内容"]

    def get_viral_patterns(self, top_n: int = 10) -> Dict:
        """
        获取爆款内容的共同模式

        Args:
            top_n: 分析前 N 个高表现内容

        Returns:
            模式分析结果
        """
        # 获取高表现内容
        top_posts = self.analytics.get_top_performing(limit=top_n)

        if not top_posts:
            self.recorder.log("warning", "📊 [爆款拆解] 没有足够的数据进行分析")
            return {}

        # 拆解每个内容
        analyses = []
        for item in top_posts:
            analysis = self.analyze_viral_content(item["draft"], item["stats"])
            analyses.append(analysis)

        # 聚合分析结果
        aggregated = self._aggregate_patterns(analyses)

        return aggregated

    def _aggregate_patterns(self, analyses: List[Dict]) -> Dict:
        """聚合多个内容的模式"""
        aggregated = {
            "total_analyzed": len(analyses),
            "title_patterns": {},
            "content_patterns": {},
            "emotion_patterns": {},
            "success_factors_frequency": {},
            "recommendations": []
        }

        # 统计标题类型
        title_types = []
        title_scores = []
        for analysis in analyses:
            title_type = analysis["patterns"]["title"]["type"]
            title_types.append(title_type)
            title_scores.append(analysis["patterns"]["title"]["score"])

        from collections import Counter
        title_type_counter = Counter(title_types)
        aggregated["title_patterns"]["most_common_type"] = title_type_counter.most_common(1)[0][0]
        aggregated["title_patterns"]["type_distribution"] = dict(title_type_counter)
        aggregated["title_patterns"]["avg_score"] = sum(title_scores) / len(title_scores)

        # 统计内容结构
        scene_based_count = sum(1 for a in analyses if a["patterns"]["content_structure"]["scene_based"])
        cta_count = sum(1 for a in analyses if a["patterns"]["content_structure"]["has_call_to_action"])
        aggregated["content_patterns"]["scene_based_ratio"] = scene_based_count / len(analyses)
        aggregated["content_patterns"]["cta_ratio"] = cta_count / len(analyses)

        # 统计情感类型
        emotion_types = [a["patterns"]["emotion"]["emotion_type"] for a in analyses]
        emotion_counter = Counter(emotion_types)
        aggregated["emotion_patterns"]["most_common_type"] = emotion_counter.most_common(1)[0][0]
        aggregated["emotion_patterns"]["type_distribution"] = dict(emotion_counter)

        # 统计成功要素
        all_factors = []
        for analysis in analyses:
            all_factors.extend(analysis["success_factors"])

        factor_counter = Counter(all_factors)
        aggregated["success_factors_frequency"] = dict(factor_counter.most_common(5))

        # 生成建议
        aggregated["recommendations"] = self._generate_recommendations(aggregated)

        return aggregated

    def _generate_recommendations(self, aggregated: Dict) -> List[str]:
        """基于模式分析生成建议"""
        recommendations = []

        # 标题建议
        most_common_title_type = aggregated["title_patterns"]["most_common_type"]
        recommendations.append(f"📌 标题建议：优先使用 {most_common_title_type} 标题")

        # 内容建议
        if aggregated["content_patterns"]["scene_based_ratio"] > 0.6:
            recommendations.append("📌 内容建议：使用场景化描述，让读者产生共鸣")

        # 情感建议
        most_common_emotion = aggregated["emotion_patterns"]["most_common_type"]
        recommendations.append(f"📌 情感建议：采用 {most_common_emotion} 情感策略")

        # 成功要素建议
        top_factors = list(aggregated["success_factors_frequency"].keys())[:3]
        if top_factors:
            recommendations.append(f"📌 关键要素：{' · '.join(top_factors)}")

        return recommendations

    def get_content_template(self, style: str = "工具推荐") -> Optional[Dict]:
        """
        获取指定风格的内容模板

        Args:
            style: 内容风格（工具推荐、教程分享、避坑指南等）

        Returns:
            内容模板字典
        """
        return self.pattern_templates.get(style)

    def apply_viral_patterns_to_content(self, content_data: Dict, patterns: Dict) -> Dict:
        """
        将爆款模式应用到新内容

        Args:
            content_data: 原始内容数据
            patterns: 爆款模式分析结果

        Returns:
            优化后的内容数据
        """
        # 这里可以根据分析结果优化内容
        # 具体实现可以结合 LLM 生成优化建议

        recommendations = patterns.get("recommendations", [])

        optimized = content_data.copy()
        optimized["optimization_notes"] = recommendations

        return optimized

    def save_analysis(self, analysis: Dict, filename: str = None):
        """保存分析结果"""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"viral_analysis_{timestamp}.json"

        save_path = Path(__file__).parent.parent / "data" / filename

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)

            self.recorder.log("info", f"📊 [爆款拆解] 分析结果已保存: {save_path}")
        except Exception as e:
            self.recorder.log("error", f"📊 [爆款拆解] 保存失败: {e}")


# 便捷函数
def get_viral_analyzer(recorder, analytics=None):
    """便捷的爆款分析器获取函数"""
    return ViralAnalyzer(recorder, analytics)


if __name__ == "__main__":
    # 测试爆款拆解功能
    from core.recorder import SessionRecorder

    recorder = SessionRecorder()
    analytics = ContentAnalytics(recorder)
    viral_analyzer = ViralAnalyzer(recorder, analytics)

    print("="*80)
    print("📊 爆款拆解测试")
    print("="*80)

    # 获取高表现内容
    top_posts = analytics.get_top_performing(limit=5)

    if top_posts:
        print(f"\n找到 {len(top_posts)} 个高表现内容")

        # 拆解第一个内容
        first_post = top_posts[0]
        print(f"\n{'='*80}")
        print("拆解第一个爆款内容")
        print(f"{'='*80}")

        analysis = viral_analyzer.analyze_viral_content(
            first_post["draft"],
            first_post["stats"]
        )

        print(f"\n📝 标题: {analysis['title']}")
        print(f"📊 评分: {analysis['score']}/100")
        print(f"\n🎯 标题特征:")
        print(f"   类型: {analysis['patterns']['title']['type']}")
        print(f"   评分: {analysis['patterns']['title']['score']}/100")
        print(f"   长度: {analysis['patterns']['title']['length']} 字符")

        print(f"\n📄 内容结构:")
        print(f"   段落数: {analysis['patterns']['content_structure']['paragraph_count']}")
        print(f"   场景化: {'是' if analysis['patterns']['content_structure']['scene_based'] else '否'}")

        print(f"\n💭 情感分析:")
        print(f"   类型: {analysis['patterns']['emotion']['emotion_type']}")
        print(f"   得分: {analysis['patterns']['emotion']['total_emotional_score']}")

        print(f"\n🏆 成功要素:")
        for factor in analysis['success_factors']:
            print(f"   {factor}")

    else:
        print("\n没有足够的数据进行分析")

    # 获取爆款模式
    print(f"\n{'='*80}")
    print("爆款模式分析")
    print(f"{'='*80}")

    patterns = viral_analyzer.get_viral_patterns(top_n=10)

    if patterns:
        print(f"\n分析内容数: {patterns['total_analyzed']}")

        print(f"\n📊 标题模式:")
        print(f"   最常见类型: {patterns['title_patterns']['most_common_type']}")
        print(f"   平均评分: {patterns['title_patterns']['avg_score']:.1f}/100")

        print(f"\n📄 内容模式:")
        print(f"   场景化比例: {patterns['content_patterns']['scene_based_ratio']:.1%}")

        print(f"\n💭 情感模式:")
        print(f"   最常见类型: {patterns['emotion_patterns']['most_common_type']}")

        print(f"\n🏆 成功要素频率:")
        for factor, count in patterns['success_factors_frequency'].items():
            print(f"   {factor}: {count} 次")

        print(f"\n💡 优化建议:")
        for rec in patterns['recommendations']:
            print(f"   {rec}")

    print("\n" + "="*80)
