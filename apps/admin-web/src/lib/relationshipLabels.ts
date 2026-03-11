import type { Member, MemberRelationship } from "../types";

type RelationType = MemberRelationship["relation_type"];

export const RELATION_TYPE_OPTIONS: Array<{ value: RelationType; label: string }> = [
  { value: "husband", label: "丈夫" },
  { value: "wife", label: "妻子" },
  { value: "spouse", label: "伴侣" },
  { value: "father", label: "爸爸" },
  { value: "mother", label: "妈妈" },
  { value: "parent", label: "父母" },
  { value: "son", label: "儿子" },
  { value: "daughter", label: "女儿" },
  { value: "child", label: "子女" },
  { value: "older_brother", label: "哥哥" },
  { value: "older_sister", label: "姐姐" },
  { value: "younger_brother", label: "弟弟" },
  { value: "younger_sister", label: "妹妹" },
  { value: "grandfather_paternal", label: "爷爷" },
  { value: "grandmother_paternal", label: "奶奶" },
  { value: "grandfather_maternal", label: "外公" },
  { value: "grandmother_maternal", label: "外婆" },
  { value: "grandson", label: "孙子" },
  { value: "granddaughter", label: "孙女" },
  { value: "guardian", label: "监护人" },
  { value: "ward", label: "被监护人" },
  { value: "caregiver", label: "照护者" },
];

const RELATION_DIRECTION_LABELS: Record<RelationType, string> = Object.fromEntries(
  RELATION_TYPE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<RelationType, string>;

const RELATION_CATEGORY_LABELS: Record<RelationType, string> = {
  husband: "伴侣",
  wife: "伴侣",
  spouse: "伴侣",
  father: "亲子",
  mother: "亲子",
  parent: "亲子",
  son: "亲子",
  daughter: "亲子",
  child: "亲子",
  older_brother: "手足",
  older_sister: "手足",
  younger_brother: "手足",
  younger_sister: "手足",
  grandfather_paternal: "祖孙",
  grandmother_paternal: "祖孙",
  grandfather_maternal: "外孙",
  grandmother_maternal: "外孙",
  grandson: "祖孙",
  granddaughter: "祖孙",
  guardian: "监护",
  ward: "监护",
  caregiver: "照护",
};

function coalesceGender(...genders: Array<Member["gender"] | undefined>): Member["gender"] {
  for (const gender of genders) {
    if (gender === "male" || gender === "female") {
      return gender;
    }
  }
  return null;
}

function inferRoleGender(
  relationType: RelationType | undefined,
  role: "source" | "target",
): Member["gender"] {
  if (role === "source") {
    return null;
  }

  switch (relationType) {
    case "husband":
    case "father":
    case "son":
    case "older_brother":
    case "younger_brother":
    case "grandfather_paternal":
    case "grandfather_maternal":
    case "grandson":
      return "male";
    case "wife":
    case "mother":
    case "daughter":
    case "older_sister":
    case "younger_sister":
    case "grandmother_paternal":
    case "grandmother_maternal":
    case "granddaughter":
      return "female";
    default:
      return null;
  }
}

function getResolvedPairGender(
  member: Member | undefined,
  relationType: RelationType,
  reverseRelationType: RelationType | undefined,
  role: "source" | "target",
): Member["gender"] {
  const reverseRole = role === "source" ? "target" : "source";
  return coalesceGender(
    member?.gender,
    inferRoleGender(relationType, role),
    inferRoleGender(reverseRelationType, reverseRole),
  );
}

function getSpouseCategoryLabel(firstGender: Member["gender"], secondGender: Member["gender"]) {
  if (firstGender === "male" && secondGender === "male") return "夫夫";
  if (firstGender === "female" && secondGender === "female") return "妻妻";
  if (
    (firstGender === "male" && secondGender === "female")
    || (firstGender === "female" && secondGender === "male")
  ) {
    return "夫妻";
  }
  return "伴侣";
}

function getParentChildCategoryLabel(parentGender: Member["gender"], childGender: Member["gender"]) {
  if (parentGender === "male") {
    if (childGender === "male") return "父子";
    if (childGender === "female") return "父女";
    return "父子/父女";
  }

  if (parentGender === "female") {
    if (childGender === "male") return "母子";
    if (childGender === "female") return "母女";
    return "母子/母女";
  }

  if (childGender === "male") return "父子/母子";
  if (childGender === "female") return "父女/母女";
  return "亲子";
}

function getSiblingCategoryLabel(olderGender: Member["gender"], youngerGender: Member["gender"]) {
  if (olderGender === "male") {
    if (youngerGender === "male") return "兄弟";
    if (youngerGender === "female") return "兄妹";
    return "兄弟/兄妹";
  }

  if (olderGender === "female") {
    if (youngerGender === "male") return "姐弟";
    if (youngerGender === "female") return "姐妹";
    return "姐弟/姐妹";
  }

  if (youngerGender === "male") return "兄弟/姐弟";
  if (youngerGender === "female") return "兄妹/姐妹";
  return "手足";
}

function inferGrandparentSide(
  relationType: RelationType,
  reverseRelationType: RelationType | undefined,
): "paternal" | "maternal" | null {
  if (
    relationType === "grandfather_maternal"
    || relationType === "grandmother_maternal"
    || reverseRelationType === "grandfather_maternal"
    || reverseRelationType === "grandmother_maternal"
  ) {
    return "maternal";
  }

  if (
    relationType === "grandfather_paternal"
    || relationType === "grandmother_paternal"
    || reverseRelationType === "grandfather_paternal"
    || reverseRelationType === "grandmother_paternal"
  ) {
    return "paternal";
  }

  return null;
}

function getGrandparentCategoryLabel(
  grandchildGender: Member["gender"],
  side: "paternal" | "maternal" | null,
) {
  const maleLabel = side === "maternal" ? "外孙" : "孙子";
  const femaleLabel = side === "maternal" ? "外孙女" : "孙女";

  if (grandchildGender === "male") return maleLabel;
  if (grandchildGender === "female") return femaleLabel;
  return `${maleLabel}/${femaleLabel}`;
}

export function getRelationDirectionLabel(relationType: RelationType) {
  return RELATION_DIRECTION_LABELS[relationType] ?? relationType;
}

export function getRelationCategoryLabel(
  relationship: MemberRelationship,
  reverseRelationship: MemberRelationship | undefined,
  sourceMember?: Member,
  targetMember?: Member,
) {
  const relationType = relationship.relation_type;
  const reverseRelationType = reverseRelationship?.relation_type;
  const sourceGender = getResolvedPairGender(sourceMember, relationType, reverseRelationType, "source");
  const targetGender = getResolvedPairGender(targetMember, relationType, reverseRelationType, "target");

  switch (relationType) {
    case "husband":
    case "wife":
    case "spouse":
      return getSpouseCategoryLabel(sourceGender, targetGender);
    case "father":
    case "mother":
    case "parent":
      return getParentChildCategoryLabel(targetGender, sourceGender);
    case "son":
    case "daughter":
    case "child":
      return getParentChildCategoryLabel(sourceGender, targetGender);
    case "older_brother":
    case "older_sister":
      return getSiblingCategoryLabel(targetGender, sourceGender);
    case "younger_brother":
    case "younger_sister":
      return getSiblingCategoryLabel(sourceGender, targetGender);
    case "grandfather_paternal":
    case "grandmother_paternal":
    case "grandfather_maternal":
    case "grandmother_maternal":
      return getGrandparentCategoryLabel(
        sourceGender,
        inferGrandparentSide(relationType, reverseRelationType),
      );
    case "grandson":
    case "granddaughter":
      return getGrandparentCategoryLabel(
        targetGender,
        inferGrandparentSide(relationType, reverseRelationType),
      );
    case "guardian":
    case "ward":
      return "监护";
    case "caregiver":
      return "照护";
    default:
      return RELATION_CATEGORY_LABELS[relationType] ?? relationType;
  }
}
