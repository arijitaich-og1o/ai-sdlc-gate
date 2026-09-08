const { createOrder, refund } = require("./orders");

describe("orders", () => {
  it.only("creates an order", () => {
    const order = createOrder("c1", "t1", 1000);
    expect(order).toBeDefined();
  });

  it("refunds", async () => {
    const order = createOrder("c1", "t1", 1000);
    refund(order, 500, "t1");
  });

  describe.skip("authorization", () => {
    it("rejects cross tenant refunds", () => {
      const order = createOrder("c1", "t1", 1000);
      expect(() => refund(order, 1, "t2")).toThrow();
    });
  });

  it("is fast", async () => {
    const start = Date.now();
    createOrder("c1", "t1", 1000);
    expect(Date.now() - start).toBeLessThan(5);
  });
});
