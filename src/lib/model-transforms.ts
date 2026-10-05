import { Box3, Group, Vector3, type Object3D } from "three";

export type Dimensions = [number, number, number];

export function modelBounds(object: Object3D) {
  object.updateMatrixWorld(true);
  const box = new Box3().setFromObject(object);
  const dimensions = box.getSize(new Vector3());
  const longest = Math.max(dimensions.x, dimensions.y, dimensions.z);
  if (!dimensions.toArray().every(Number.isFinite) || longest <= 0) {
    throw new Error("The model has empty or invalid geometry bounds.");
  }
  return { dimensions, center: box.getCenter(new Vector3()), scale: 4.6 / longest };
}

/** Create a centred axle pivot while retaining the wheel's visible world transform. */
export function wheelPivot(scene: Object3D, name: string) {
  const wheel = scene.getObjectByName(name);
  if (!wheel) return null;
  if (wheel.userData.pivotAtAxle || !wheel.parent) return wheel;
  const parent = wheel.parent;
  scene.updateMatrixWorld(true);
  const center = new Box3().setFromObject(wheel).getCenter(new Vector3());
  // Metadata describes the wheel's local axis. The new pivot uses the parent's axes.
  const axis = new Vector3().fromArray(wheel.userData.wheelAxis ?? [0, 0, 1])
    .applyQuaternion(wheel.quaternion).normalize();
  const pivot = new Group();
  pivot.name = `${name}AxlePivot`;
  parent.add(pivot);
  pivot.position.copy(parent.worldToLocal(center));
  pivot.updateMatrixWorld(true);
  pivot.attach(wheel);
  pivot.userData.wheelAxis = axis.toArray();
  pivot.userData.pivotAtAxle = true;
  return pivot;
}

/** Fit every corner of the actual bounds, including depth, into a perspective view. */
export function fittedCameraPosition(dimensions: Dimensions, direction: Vector3, aspect: number, fov = 37, margin = 1.12) {
  if (!dimensions.every((value) => Number.isFinite(value) && value >= 0) ||
      Math.max(...dimensions) <= 0 || !Number.isFinite(aspect) || aspect <= 0) {
    throw new RangeError("Camera fitting requires finite model bounds and a positive aspect ratio.");
  }
  const forward = direction.clone().normalize();
  const right = new Vector3(0, 1, 0).cross(forward).normalize();
  const up = forward.clone().cross(right).normalize();
  const tan = Math.tan(fov * Math.PI / 360);
  let distance = 1.5;
  for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
    const corner = new Vector3(x * dimensions[0] / 2, y * dimensions[1] / 2, z * dimensions[2] / 2);
    const projected = Math.max(Math.abs(corner.dot(right)) / (tan * aspect), Math.abs(corner.dot(up)) / tan);
    distance = Math.max(distance, corner.dot(forward) + projected);
  }
  return forward.multiplyScalar(distance * margin);
}

/**
 * World-space offset for "Move the View" (Blender's hand / Shift+MMB pan): the picture follows the pointer,
 * so dragging right/down moves the scene right/down. Matches OrbitControls' screen-space panning: a drag
 * across the full viewport height moves the view by the visible height at the orbit target.
 */
export function panOffset(position: Vector3, target: Vector3, right: Vector3, up: Vector3, fov: number,
                          viewportHeight: number, dx: number, dy: number) {
  const visibleHeight = 2 * position.distanceTo(target) * Math.tan(fov * Math.PI / 360);
  const perPixel = visibleHeight / Math.max(1, viewportHeight);
  return right.clone().normalize().multiplyScalar(-dx * perPixel).addScaledVector(up.clone().normalize(), dy * perPixel);
}
