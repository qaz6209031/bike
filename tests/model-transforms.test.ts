import test from "node:test";
import assert from "node:assert/strict";
import { Box3, Group, Mesh, MeshStandardMaterial, Quaternion, TorusGeometry, Vector3 } from "three";
import { fittedCameraPosition, modelBounds, wheelPivot, type Dimensions } from "../src/lib/model-transforms.ts";

test("an unmarked, rotated wheel gets a centred pivot without moving its geometry", () => {
  const scene = new Group();
  const parent = new Group();
  parent.position.set(1, 0.2, -0.5);
  parent.rotation.set(0.2, 0.5, 0.1);
  scene.add(parent);
  const wheel = new Mesh(new TorusGeometry(0.4, 0.03, 16, 64), new MeshStandardMaterial());
  wheel.name = "RearWheel";
  wheel.position.set(-0.3, 0.7, 0.1);
  wheel.rotation.set(0.7, 0.4, 0.3);
  parent.add(wheel);
  scene.updateMatrixWorld(true);
  const before = new Box3().setFromObject(wheel);
  const normal = new Vector3(0, 0, 1).applyQuaternion(wheel.getWorldQuaternion(new Quaternion()));
  const pivot = wheelPivot(scene, "RearWheel")!;
  scene.updateMatrixWorld(true);
  const after = new Box3().setFromObject(wheel);
  assert.ok(before.min.distanceTo(after.min) < 1e-6);
  assert.ok(before.max.distanceTo(after.max) < 1e-6);
  assert.ok(pivot.getWorldPosition(new Vector3()).distanceTo(before.getCenter(new Vector3())) < 1e-6);
  const axis = new Vector3().fromArray(pivot.userData.wheelAxis);
  const worldAxis = axis.clone().applyQuaternion(pivot.getWorldQuaternion(new Quaternion()));
  assert.ok(worldAxis.distanceTo(normal) < 1e-6, "the pivot axle preserves the exported wheel orientation");
  pivot.rotateOnAxis(axis, Math.PI / 2);
  scene.updateMatrixWorld(true);
  const spun = new Box3().setFromObject(wheel);
  assert.ok(spun.getCenter(new Vector3()).distanceTo(before.getCenter(new Vector3())) < 1e-6);
  assert.ok(spun.getSize(new Vector3()).distanceTo(before.getSize(new Vector3())) < 1e-6);
  wheel.geometry.dispose();
  wheel.material.dispose();
});

test("a properly marked exported axle pivot is preserved", () => {
  const scene = new Group();
  const wheel = new Group();
  wheel.name = "FrontWheel";
  wheel.userData.pivotAtAxle = true;
  scene.add(wheel);
  assert.equal(wheelPivot(scene, "FrontWheel"), wheel);
  assert.equal(wheelPivot(scene, "RearWheel"), null);
});

for (const aspect of [0.55, 1, 1.8]) {
  test(`camera fitting contains all bounds corners at aspect ratio ${aspect}`, () => {
    const dimensions: Dimensions = [4.6, 3.7, 1.6];
    for (const direction of [new Vector3(1.6, 0.85, 3.4), new Vector3(0, 0.1, 1), new Vector3(1, 0.1, 0.035)]) {
      const position = fittedCameraPosition(dimensions, direction, aspect);
      const forward = position.clone().normalize();
      const right = new Vector3(0, 1, 0).cross(forward).normalize();
      const up = forward.clone().cross(right).normalize();
      const tan = Math.tan(37 * Math.PI / 360);
      for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
        const corner = new Vector3(x * dimensions[0] / 2, y * dimensions[1] / 2, z * dimensions[2] / 2);
        const depth = position.length() - corner.dot(forward);
        assert.ok(Math.abs(corner.dot(right)) < depth * tan * aspect);
        assert.ok(Math.abs(corner.dot(up)) < depth * tan);
      }
    }
  });
}

test("empty geometry fails cleanly instead of producing infinite scale", () => {
  assert.throws(() => modelBounds(new Group()), /empty or invalid/);
  assert.throws(() => fittedCameraPosition([0, 0, 0], new Vector3(0, 0, 1), 1), RangeError);
});
