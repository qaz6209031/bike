import test from "node:test";
import assert from "node:assert/strict";
import { radiansToRpm, rpmToRadians, WheelDrive } from "../src/lib/wheel-physics.ts";

test("wheel slowdown and angular travel are independent of frame rate", () => {
  function simulate(fps: number) {
    const drive = new WheelDrive();
    drive.setVelocity("RearWheel", rpmToRadians(180));
    let angle = 0;
    for (let i = 0; i < fps * 3; i++) {
      angle += drive.step(1 / fps).RearWheel;
    }
    return { omega: drive.velocities.RearWheel, angle };
  }
  const a = simulate(30);
  const b = simulate(144);
  assert.ok(Math.abs(a.omega - b.omega) < 1e-10);
  assert.ok(Math.abs(a.angle - b.angle) < 1e-10);
  assert.ok(a.omega < rpmToRadians(180));
});

test("fixed background friction brings both wheels to rest and Brake stops immediately", () => {
  const drive = new WheelDrive();
  drive.setVelocity("both", 12);
  const travel = drive.step(0.5);
  assert.ok(travel.FrontWheel > 0 && travel.FrontWheel < 6);
  assert.equal(travel.FrontWheel, travel.RearWheel);
  assert.ok(drive.velocities.FrontWheel > 0 && drive.velocities.FrontWheel < 12);
  drive.step(3600);
  assert.deepEqual(drive.velocities, { FrontWheel: 0, RearWheel: 0 });
  drive.setVelocity("both", 12);
  drive.stop();
  assert.deepEqual(drive.step(1), { FrontWheel: 0, RearWheel: 0 });
  assert.equal(radiansToRpm(rpmToRadians(180)), 180);
});

test("rear-wheel impulses never spin the front wheel", () => {
  const drive = new WheelDrive();
  drive.addImpulse("RearWheel", 15);
  drive.addImpulse("RearWheel", 5);
  assert.equal(drive.velocities.RearWheel, 20);
  assert.equal(drive.velocities.FrontWheel, 0);
  drive.step(1);
  assert.ok(drive.velocities.RearWheel > 0 && drive.velocities.RearWheel < 20);
  drive.stop();
  assert.deepEqual(drive.velocities, { FrontWheel: 0, RearWheel: 0 });
});

test("reverse rotation is supported and invalid timing/velocity is rejected", () => {
  const drive = new WheelDrive();
  drive.setVelocity("FrontWheel", -12);
  const travel = drive.step(0.5);
  assert.ok(travel.FrontWheel < 0 && travel.FrontWheel > -6);
  assert.equal(travel.RearWheel, 0);
  assert.throws(() => drive.step(-1), RangeError);
  assert.throws(() => drive.step(NaN), RangeError);
  assert.throws(() => drive.setVelocity("RearWheel", Infinity), RangeError);
  assert.throws(() => drive.addImpulse("RearWheel", NaN), RangeError);
});

test("the stop threshold produces the same total rotation at different frame rates", () => {
  function simulate(fps: number) {
    const drive = new WheelDrive();
    drive.setVelocity("RearWheel", rpmToRadians(180));
    let angle = 0;
    for (let i = 0; i < fps * 60; i++) angle += drive.step(1 / fps).RearWheel;
    assert.equal(drive.velocities.RearWheel, 0);
    return angle;
  }
  assert.ok(Math.abs(simulate(30) - simulate(144)) < 1e-9);
});

test("lower friction retains more than half the initial speed after five seconds", () => {
  const drive = new WheelDrive();
  drive.setVelocity("RearWheel", rpmToRadians(180));
  drive.step(5);
  assert.ok(radiansToRpm(drive.velocities.RearWheel) > 90);
  assert.ok(radiansToRpm(drive.velocities.RearWheel) < 180);
});
