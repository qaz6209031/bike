export type WheelName = "FrontWheel" | "RearWheel";
export type WheelTarget = WheelName | "both";

export const rpmToRadians = (rpm: number) => (rpm * Math.PI * 2) / 60;
export const radiansToRpm = (omega: number) => (omega * 60) / (Math.PI * 2);

// Fixed studio tuning; friction is deliberately absent from the viewer controls.
export const COAST_DAMPING = 0.12;
const STOP_SPEED = 0.025;

/** Exact integration keeps decay and angular travel independent of frame rate. */
function coastStep(omega: number, seconds: number) {
  const speed = Math.abs(omega);
  if (speed <= STOP_SPEED) return { omega: 0, angle: 0 };
  const untilStop = Math.log(speed / STOP_SPEED) / COAST_DAMPING;
  const elapsed = Math.min(seconds, untilStop);
  const next = omega * Math.exp(-COAST_DAMPING * elapsed);
  return { omega: seconds >= untilStop ? 0 : next, angle: (omega - next) / COAST_DAMPING };
}

export class WheelDrive {
  velocities: Record<WheelName, number> = { FrontWheel: 0, RearWheel: 0 };

  setVelocity(target: WheelTarget, radiansPerSecond: number) {
    if (!Number.isFinite(radiansPerSecond)) throw new RangeError("Velocity must be finite.");
    this.each(target, (name) => { this.velocities[name] = radiansPerSecond; });
  }

  /** Connect a future pointer/touch flick recognizer here, in rad/s. */
  addImpulse(target: WheelTarget, radiansPerSecond: number) {
    if (!Number.isFinite(radiansPerSecond)) throw new RangeError("Impulse must be finite.");
    this.each(target, (name) => { this.velocities[name] += radiansPerSecond; });
  }

  stop() {
    this.velocities.FrontWheel = 0;
    this.velocities.RearWheel = 0;
  }

  step(seconds: number): Record<WheelName, number> {
    if (!Number.isFinite(seconds) || seconds < 0) throw new RangeError("Elapsed time must be finite and nonnegative.");
    const front = coastStep(this.velocities.FrontWheel, seconds);
    const rear = coastStep(this.velocities.RearWheel, seconds);
    this.velocities.FrontWheel = front.omega;
    this.velocities.RearWheel = rear.omega;
    return { FrontWheel: front.angle, RearWheel: rear.angle };
  }

  private each(target: WheelTarget, fn: (name: WheelName) => void) {
    if (target === "both") {
      fn("FrontWheel");
      fn("RearWheel");
    } else fn(target);
  }
}
