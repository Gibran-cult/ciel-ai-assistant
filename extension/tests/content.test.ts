test("the content script exposes act and observe once", async () => {
  await import("../src/content/index");
  const first = (globalThis as { cielAgent?: object }).cielAgent;
  expect(first).toMatchObject({ act: expect.any(Function), observe: expect.any(Function) });
  expect(Object.isFrozen(first)).toBe(true);
});
