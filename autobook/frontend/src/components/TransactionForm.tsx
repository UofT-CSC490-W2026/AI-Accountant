type TransactionFormProps = {
  value: string;
  onChange: (value: string) => void;
  selectedFileName: string | null;
  onFileChange: (file: File | null) => void;
  onSubmit: () => void;
  onUploadFile: () => void;
  isLoading: boolean;
};

export function TransactionForm({
  value,
  onChange,
  selectedFileName,
  onFileChange,
  onSubmit,
  onUploadFile,
  isLoading,
}: TransactionFormProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Input</p>
          <h2>Manual Text, CSV, or PDF</h2>
        </div>
      </div>

      <label className="field-label" htmlFor="transaction-input">
        Describe a transaction in plain language
      </label>
      <p className="field-help">
        Include amount, counterparty, and action when possible. Cleaner wording should clear the
        confidence threshold faster.
      </p>
      <textarea
        id="transaction-input"
        className="text-area"
        rows={5}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Example: Bought a laptop for $2400"
      />

      <div className="file-upload-grid">
        <div>
          <label className="field-label" htmlFor="transaction-file-upload">
            Upload transaction file
          </label>
          <p className="field-help">
            Supported upload paths: CSV and text-based PDF. The frontend labels each upload explicitly so downstream services can dispatch to the right normalizer path.
          </p>
          <input
            id="transaction-file-upload"
            className="text-input"
            type="file"
            accept=".csv,text/csv,.pdf,application/pdf"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          />
          <span className="file-selection-copy">
            {selectedFileName ? `Selected file: ${selectedFileName}` : "No file selected yet."}
          </span>
          <div className="sample-link-row">
            <a href="/sample-csv/clean-purchase.csv" target="_blank" rel="noreferrer">
              Sample clean CSV
            </a>
            <a href="/sample-csv/ambiguous-transfer.csv" target="_blank" rel="noreferrer">
              Sample clarification CSV
            </a>
            <a href="/sample-csv/invoice-demo.pdf" target="_blank" rel="noreferrer">
              Sample PDF
            </a>
          </div>
        </div>
      </div>

      <div className="panel-actions">
        <button className="primary-button" onClick={onSubmit} disabled={isLoading || !value.trim()}>
          {isLoading ? "Parsing..." : "Parse Transaction"}
        </button>
        <button
          className="secondary-button"
          onClick={onUploadFile}
          disabled={isLoading || !selectedFileName}
        >
          {isLoading ? "Processing..." : "Upload File"}
        </button>
      </div>
    </section>
  );
}
