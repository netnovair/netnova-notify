import {
  BellRing,
  FolderKanban,
  Home,
  KeyRound,
  Settings,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  group: "main" | "manage" | "system";
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "خانه", shortLabel: "خانه", icon: Home, group: "main" },
  {
    href: "/projects",
    label: "پروژه ها",
    shortLabel: "پروژه ها",
    icon: FolderKanban,
    group: "manage",
  },
  {
    href: "/notifications",
    label: "تاریخچه ارسال",
    shortLabel: "اطلاعیه ها",
    icon: BellRing,
    group: "manage",
  },
  {
    href: "/licenses",
    label: "لایسنس ها",
    shortLabel: "لایسنس ها",
    icon: KeyRound,
    group: "manage",
  },
  {
    href: "/payments",
    label: "پرداخت ها",
    shortLabel: "پرداخت ها",
    icon: Wallet,
    group: "manage",
  },
  {
    href: "/settings",
    label: "تنظیمات",
    shortLabel: "تنظیمات",
    icon: Settings,
    group: "system",
  },
];

export const MOBILE_NAV_ITEMS = NAV_ITEMS.filter((item) =>
  ["/", "/projects", "/notifications", "/payments", "/settings"].includes(item.href),
);

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
