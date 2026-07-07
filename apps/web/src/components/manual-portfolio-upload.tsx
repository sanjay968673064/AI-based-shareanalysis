"use client";

import { useMutation } from "@tanstack/react-query";
import { FileSpreadsheet, Upload, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { uploadManualPortfolioCsv } from "@/lib/api";

export function ManualPortfolioUpload({ onImported }: { onImported: () => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: uploadManualPortfolioCsv,
    onSuccess: (result) => {
      setMessage(`${result.importedCount} holdings imported. ${result.skippedCount} rows skipped.`);
      setFile(null);
      onImported();
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : "Unable to import portfolio CSV.");
    }
  });

  function importFile(selectedFile: File) {
    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setMessage("Select a .csv file.");
      setFile(null);
      return;
    }
    setFile(selectedFile);
    setMessage(`Uploading ${selectedFile.name}...`);
    mutation.mutate(selectedFile);
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    if (!file) {
      setMessage("Select a CSV file to import.");
      return;
    }
    mutation.mutate(file);
  }

  return (
    <>
      <Button variant="ghost" onClick={() => setIsOpen(true)}>
        <Upload size={18} />
        Upload CSV
      </Button>

      {isOpen ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 px-4 py-6 backdrop-blur-sm sm:items-center">
          <form
            onSubmit={handleSubmit}
            className="my-auto w-full max-w-lg rounded-lg border border-border bg-panel p-5 shadow-glow"
          >
            <div className="mb-5 flex items-start justify-between gap-3">
              <div className="flex gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent text-black">
                  <FileSpreadsheet size={20} />
                </div>
                <div>
                  <h2 className="text-base font-semibold">Upload Portfolio CSV</h2>
                  <p className="mt-1 text-sm text-muted">This replaces the current manual holdings.</p>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setIsOpen(false)}
                className="rounded-md border border-border bg-white/5 p-2 text-muted transition hover:bg-white/10 hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>

            <label className="mb-4 block">
              <span className="mb-2 block text-sm text-muted">Portfolio CSV file</span>
              <input
                type="file"
                accept=".csv,text/csv"
                disabled={mutation.isPending}
                onChange={(event) => {
                  const selectedFile = event.target.files?.[0];
                  if (selectedFile) {
                    importFile(selectedFile);
                  }
                  event.target.value = "";
                }}
                className="block w-full rounded-md border border-border bg-black/30 px-3 py-3 text-sm text-muted file:mr-3 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-2 file:text-sm file:font-medium file:text-black"
              />
            </label>

            <div className="mb-4 rounded-md border border-border bg-black/20 p-3 text-sm text-muted">
              Select a CSV to import immediately. Supported columns include Name, Buy Quantity, Average Price, Last
              Price, Sector, Symbol, Quantity, LTP, P&L and Day chg.
            </div>

            {message ? (
              <p className={`mb-4 text-sm ${mutation.isError ? "text-loss" : "text-profit"}`}>{message}</p>
            ) : null}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setIsOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                <Upload size={18} />
                {mutation.isPending ? "Importing" : "Import"}
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
