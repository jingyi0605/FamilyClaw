export const ROOM_TYPE_OPTIONS = [
  { value: "living_room", label: "客厅" },
  { value: "bedroom", label: "卧室" },
  { value: "study", label: "书房" },
  { value: "entrance", label: "玄关" },
  { value: "kitchen", label: "厨房" },
  { value: "bathroom", label: "卫生间" },
  { value: "gym", label: "健身房" },
  { value: "garage", label: "车库" },
  { value: "dining_room", label: "餐厅" },
  { value: "balcony", label: "阳台" },
  { value: "kids_room", label: "儿童房" },
  { value: "storage_room", label: "储物间" },
] as const;

export type RoomType = (typeof ROOM_TYPE_OPTIONS)[number]["value"];

const ROOM_TYPE_LABELS: Record<RoomType, string> = Object.fromEntries(
  ROOM_TYPE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<RoomType, string>;

export function formatRoomType(roomType: RoomType) {
  return ROOM_TYPE_LABELS[roomType];
}
