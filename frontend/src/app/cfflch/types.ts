export type PdfUrl = { url: string; search_title: string };

export type ClassRoom = { id: number; name: string };

export type SavedAdmissionResult = {
  id: number;
  student_name: string;
  year: number;
  approved: boolean;
  class_room_id: number | null;
  created_at: string;
  pdf_urls: PdfUrl[] | undefined;
};