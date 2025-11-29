import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader2, AlertCircle, X } from 'lucide-react';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isLoading: boolean;
  error?: string | null;
  onDismissError?: () => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({ 
  onFileSelect, 
  isLoading, 
  error, 
  onDismissError 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
      // Reset the input value to allow re-selecting the same file if needed (e.g. after error)
      e.target.value = '';
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto mt-10">
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-red-700 animate-in fade-in slide-in-from-top-2">
          <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="font-semibold text-sm">Upload Failed</h3>
            <p className="text-sm mt-1 opacity-90">{error}</p>
          </div>
          {onDismissError && (
            <button 
              onClick={(e) => {
                e.stopPropagation();
                onDismissError();
              }} 
              className="text-red-400 hover:text-red-600 transition-colors p-1"
              aria-label="Dismiss error"
            >
              <X size={18} />
            </button>
          )}
        </div>
      )}

      <div
        onClick={!isLoading ? handleClick : undefined}
        onDragOver={!isLoading ? handleDragOver : undefined}
        onDragLeave={!isLoading ? handleDragLeave : undefined}
        onDrop={!isLoading ? handleDrop : undefined}
        className={`
          relative flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-xl transition-all duration-300 cursor-pointer
          ${isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50'}
          ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
          ${error ? 'border-red-300 bg-red-50/30' : ''}
        `}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleInputChange}
          className="hidden"
          accept=".xlsx,.xls,.csv,.pdf"
          disabled={isLoading}
        />

        {isLoading ? (
          <div className="flex flex-col items-center animate-pulse">
            <Loader2 className="w-16 h-16 text-indigo-600 animate-spin mb-4" />
            <p className="text-lg font-medium text-slate-700">Analyzing Statement...</p>
            <p className="text-sm text-slate-500 mt-2">This usually takes a few seconds</p>
          </div>
        ) : (
          <>
            <div className={`p-4 rounded-full bg-indigo-50 mb-4 ${isDragging ? 'scale-110' : ''} transition-transform`}>
              <UploadCloud className="w-10 h-10 text-indigo-600" />
            </div>
            <h3 className="text-xl font-semibold text-slate-800 mb-2">
              Upload Bank Statement
            </h3>
            <p className="text-slate-500 text-center mb-6 max-w-xs">
              Drag & drop your PDF, Excel or CSV file here, or click to browse
            </p>
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-lg text-sm text-slate-600 font-medium">
              <FileText className="w-4 h-4" />
              <span>Supported: .pdf, .xlsx, .xls, .csv</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
