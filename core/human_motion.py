import asyncio
import random
from playwright.async_api import Page

class HumanMotion:
    def __init__(self, page: Page):
        self.page = page

    async def _bezier_move(self, target_x, target_y):
        """内部贝塞尔曲线生成与移动"""
        # 简单的起点逻辑：假设从屏幕中心或随机点开始
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)
        
        # 两个控制点，制造弧线
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.8)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.2, 0.8) + random.randint(-50, 50)
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.8)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.2, 0.8) + random.randint(-50, 50)

        steps = random.randint(15, 30)
        for i in range(steps + 1):
            t = i / steps
            # 三阶贝塞尔公式
            x = (1-t)**3*start_x + 3*(1-t)**2*t*cp1_x + 3*(1-t)*t**2*cp2_x + t**3*target_x
            y = (1-t)**3*start_y + 3*(1-t)**2*t*cp1_y + 3*(1-t)*t**2*cp2_y + t**3*target_y
            
            await self.page.mouse.move(x, y)
            # 极短停顿模拟人手的不稳定性
            await asyncio.sleep(random.uniform(0.001, 0.005))

    async def click_element(self, selector_list, action_name="Click"):
        """支持选择器列表的健壮点击"""
        # 归一化为列表
        selectors = selector_list if isinstance(selector_list, list) else [selector_list]
        
        for sel in selectors:
            try:
                locator = self.page.locator(sel).first
                if await locator.is_visible():
                    box = await locator.bounding_box()
                    if box:
                        # 目标点：元素中心加随机偏移
                        tx = box["x"] + box["width"]/2 + random.uniform(-5, 5)
                        ty = box["y"] + box["height"]/2 + random.uniform(-5, 5)
                        
                        await self._bezier_move(tx, ty)
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                        await self.page.mouse.click(tx, ty)
                        print(f"  └─ [{action_name}] 成功: {sel}")
                        return True
            except Exception:
                continue
        return False

    async def human_scroll(self, distance: int = 500):
        """变速滚动"""
        scrolled = 0
        while scrolled < distance:
            step = random.randint(50, 150)
            await self.page.mouse.wheel(0, step)
            scrolled += step
            # 随机停顿，看点东西
            if random.random() < 0.3:
                await asyncio.sleep(random.uniform(0.5, 1.2))
            else:
                await asyncio.sleep(random.uniform(0.05, 0.2))