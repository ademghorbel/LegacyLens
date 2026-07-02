"""Simple inventory tracker."""

class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = self.items.get(sku, 0) + qty

    def remove(self, sku, qty):
        if self.items.get(sku, 0) < qty:
            raise ValueError(f"Not enough stock for {sku}")
        self.items[sku] -= qty

    def report(self):
        return {k: v for k, v in self.items.items() if v > 0}
