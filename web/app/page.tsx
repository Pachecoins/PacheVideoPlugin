import { redirect } from "next/navigation";

// The public root opens the product itself. The former landing page remains
// available in Git history for future marketing campaigns.
export default function HomePage() {
  redirect("/app");
}
