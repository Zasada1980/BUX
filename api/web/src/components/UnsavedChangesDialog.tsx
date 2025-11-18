import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface UnsavedChangesDialogProps {
  open: boolean;
  onStay: () => void;
  onLeave: () => void;
}

export function UnsavedChangesDialog({ open, onStay, onLeave }: UnsavedChangesDialogProps) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Несохранённые изменения</AlertDialogTitle>
          <AlertDialogDescription>
            У вас есть несохранённые изменения в меню бота. Если уйти со страницы, они будут потеряны.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onStay}>Остаться на странице</AlertDialogCancel>
          <AlertDialogAction onClick={onLeave} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
            Уйти без сохранения
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
