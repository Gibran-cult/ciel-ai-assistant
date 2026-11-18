// @vitest-environment node
import { vi } from "vitest";
import { Session, type SessionDeps } from "../src/stop";
import { isUserInput } from "../src/content/takeover";

function setup(online = true) {
  const deps = {
    socket: { sendStop: vi.fn(() => online), answer: vi.fn(() => true) },
    runner: { onAction: vi.fn(async (_signed: unknown): Promise<void> => undefined), end: vi.fn(), taskTab: 1 as number | null },
    refuse: vi.fn(),
    show: vi.fn(),
  } satisfies SessionDeps;
  const session = new Session(deps);
  session.begin();
  return { session, deps };
}

const ACTION = { ticket: { task: "t1", seq: 3 } };
const flush = () => new Promise((done) => setTimeout(done, 0));

test("actions run one after another while running", async () => {
  const { session, deps } = setup();
  const order: number[] = [];
  deps.runner.onAction.mockImplementation(async (signed: unknown) => {
    await flush();
    order.push((signed as { n: number }).n);
  });
  session.onAction({ n: 1 });
  session.onAction({ n: 2 });
  await session.idle();
  expect(order).toEqual([1, 2]);
});

test("stop empties the queue, ends the task on the device first, then sends stop", async () => {
  const { session, deps } = setup();
  session.takeover(1);
  session.onAction(ACTION);
  session.stop();
  expect(deps.runner.end).toHaveBeenCalled();
  expect(deps.socket.sendStop).toHaveBeenCalledTimes(1);
  expect(deps.runner.end.mock.invocationCallOrder[0]!).toBeLessThan(deps.socket.sendStop.mock.invocationCallOrder[0]!);
  session.resume();
  await session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
  expect(session.phase).toBe("stopped");
});

test("after stop, even offline, new actions are refused until a new task starts", async () => {
  const { session, deps } = setup(false);
  session.stop();
  session.onAction(ACTION);
  await session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
  expect(deps.refuse).toHaveBeenCalledWith(ACTION, "stopped");

  session.begin();
  session.onAction(ACTION);
  await session.idle();
  expect(deps.runner.onAction).toHaveBeenCalledTimes(1);
});

test("stop while an action is running lets nothing after it run", async () => {
  const { session, deps } = setup();
  let release!: () => void;
  deps.runner.onAction.mockImplementationOnce(() => new Promise<void>((done) => (release = done)));
  session.onAction({ n: 1 });
  session.onAction({ n: 2 });
  await flush();
  session.stop();
  release();
  await session.idle();
  expect(deps.runner.onAction).toHaveBeenCalledTimes(1);
});

test("the user's own input on the task tab pauses the queue until they decide", async () => {
  const { session, deps } = setup();
  session.takeover(1);
  expect(session.phase).toBe("paused");
  session.onAction(ACTION);
  await session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
  expect(deps.show).toHaveBeenLastCalledWith(expect.objectContaining({ phase: "paused" }));

  session.resume();
  await session.idle();
  expect(deps.runner.onAction).toHaveBeenCalledWith(ACTION);
});

test("input on another tab, or when idle, does not pause", () => {
  const { session } = setup();
  session.takeover(2);
  expect(session.phase).toBe("running");
  session.stop();
  session.takeover(1);
  expect(session.phase).toBe("stopped");
});

test("during a handover the page is never read, and only Lanjutkan turns it back on", async () => {
  const { session, deps } = setup();
  session.onHandover(12);
  expect(session.phase).toBe("handover");
  session.onAction(ACTION);
  await session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
  expect(deps.refuse).toHaveBeenCalledWith(ACTION, "handover");

  session.resume();
  expect(session.phase).toBe("handover");
  session.finishHandover(true);
  expect(deps.socket.answer).toHaveBeenCalledWith(12, true);
  expect(session.phase).toBe("running");
});

test("declining a handover answers false and stays off the page", () => {
  const { session, deps } = setup();
  session.onHandover(5);
  session.finishHandover(false);
  expect(deps.socket.answer).toHaveBeenCalledWith(5, false);
});

test("the task ending clears everything", async () => {
  const { session, deps } = setup();
  session.takeover(1);
  session.onAction(ACTION);
  session.onEnd();
  expect(session.phase).toBe("idle");
  session.onAction(ACTION);
  await session.idle();
  expect(deps.runner.onAction).not.toHaveBeenCalled();
});

test("only real user input counts as taking over", () => {
  expect(isUserInput({ isTrusted: true, type: "keydown" })).toBe(true);
  expect(isUserInput({ isTrusted: true, type: "pointerdown" })).toBe(true);
  expect(isUserInput({ isTrusted: false, type: "keydown" })).toBe(false);
  expect(isUserInput({ isTrusted: true, type: "scroll" })).toBe(false);
});
