export const PARTS = [
  { name: "Frame", label: "Frame & fork", detail: "Endurace CF SLX · size S · FK0165 CF fork", category: "FRAMESET" },
  { name: "FrontWheel", label: "Front wheel", detail: "Canyon ED42 CF · ENVE stickers · Pro One Evo 32 mm", category: "WHEELS" },
  { name: "RearWheel", label: "Rear wheel", detail: "Canyon ED42 CF · ENVE stickers · Pro One Evo 32 mm", category: "WHEELS" },
  { name: "FrontHub", label: "Front hub", detail: "DT Swiss 350", category: "WHEELS" },
  { name: "RearHub", label: "Freehub upgrade", detail: "DT Swiss 350 · 54T ratchet · upgraded from 36T", category: "WHEELS" },
  { name: "Crank", label: "Crankset", detail: "SRAM Rival · 48/35T · 165 mm · DUB PF86.5", category: "DRIVETRAIN" },
  { name: "PowerMeter", label: "Power meter", detail: "SRAM DUB PM Spindle", category: "DRIVETRAIN" },
  { name: "Pedals", label: "Pedals", detail: "Shimano PD-R550", category: "DRIVETRAIN" },
  { name: "FrontDerailleur", label: "Front derailleur", detail: "SRAM Rival AXS E1", category: "DRIVETRAIN" },
  { name: "RearDerailleur", label: "Rear derailleur", detail: "SRAM Rival eTap AXS", category: "DRIVETRAIN" },
  { name: "Drivetrain", label: "Cassette & chain", detail: "Rival XG-1250 · 10–36T · 12-speed · Rival E1 chain", category: "DRIVETRAIN" },
  { name: "Brakes", label: "Brakes", detail: "SRAM Rival AXS · Paceline 160 mm rotors", category: "DRIVETRAIN" },
  { name: "FrontLight", label: "Front light", detail: "Front light", category: "ACCESSORIES" },
  { name: "RearLight", label: "Rear light", detail: "Canyon FLASH Cycling Rear Light", category: "ACCESSORIES" },
  { name: "Cockpit", label: "Cockpit & stem", detail: "Canyon PACE T-bar · 80 mm stem", category: "ACCESSORIES" },
  { name: "Stem", label: "Stem", detail: "Canyon CP0048 PACE · 80 mm", category: "ACCESSORIES" },
  { name: "BikeComputer", label: "Bike computer", detail: "Bryton S510", category: "ACCESSORIES" },
  { name: "ComputerMount", label: "Computer mount", detail: "Canyon GEAR GROOVE Computer Mount", category: "ACCESSORIES" },
  { name: "BottleCages", label: "Bottle cages", detail: "HUALONG 3K Carbon Fiber Bicycle Water Bottle Cage", category: "ACCESSORIES" },
  { name: "NameSticker", label: "Name sticker", detail: "VeloInk · Kai name sticker · veloink.com", category: "ACCESSORIES" },
  { name: "EnveDecals", label: "ENVE white decal stickers", detail: "White ENVE rim decals · Canyon ED42 CF wheels", category: "ACCESSORIES", objectNames: ["FrontEnveDecals", "RearEnveDecals"] },
  { name: "Saddle", label: "Saddle & seatpost", detail: "Fizik Aliante R5 · SP0093 VCLS Aero carbon post", category: "ACCESSORIES" },
] as const;

export type PartName = (typeof PARTS)[number]["name"];
export function partObjectNames(part: (typeof PARTS)[number]): readonly string[] {
  return "objectNames" in part ? part.objectNames : [part.name];
}
// Keep the complete object registry for wheel controls; show only the owner's additions.
const OWNER_UPGRADE_ORDER = ["RearLight", "Cockpit", "BottleCages", "BikeComputer", "ComputerMount", "RearHub", "Pedals", "NameSticker", "EnveDecals"] as const satisfies readonly PartName[];
export const UPGRADE_PARTS = OWNER_UPGRADE_ORDER.map((name) => PARTS.find((part) => part.name === name)!);
export type CameraView = "perspective" | "side" | "front";
export const BIKE_SIZE = "S";
export const COMPONENT_SOURCE = "https://www.canyon.com/en-us/road-bikes/endurance-bikes/endurace/cf-slx/endurace-cf-slx-7-axs/4431.html?dwvar_4431_pv_rahmenfarbe=R130_P01";
export const MODEL_URL = "/models/endurace.glb?v=ae6121c16dde";
export const ENVIRONMENT_URL = "/environment/studio.hdr";
