/** The photo chip appears only when a photo is attached or the message asks for one. */

const PHOTO_ASK = /фото|картин|иллюстрац|изображен/i;

export function asksForPhoto(text: string): boolean {
  return PHOTO_ASK.test(text || "");
}

export function photoLimitChip(args: {
  text: string;
  attached: number;
  maxImages: number;
  forbidImages: boolean;
  showLimits: boolean;
}): string | null {
  if (args.attached > 0) return `фото ×${args.attached}`;
  if (!args.showLimits || !asksForPhoto(args.text)) return null;
  if (args.forbidImages) return "без фото";
  return `≤${Math.max(args.maxImages, 0)} фото`;
}
