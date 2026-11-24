import { ErrorNotice } from "@/components/ui";

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="mb-4">
      <ErrorNotice>{message}</ErrorNotice>
    </div>
  );
}
