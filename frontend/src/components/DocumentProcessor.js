import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import { 
  Upload, 
  FileText, 
  Download, 
  Settings, 
  MessageCircle,
  Sun, 
  Moon,
  Brain,
  Sparkles,
  FileSearch,
  BookOpen,
  Network,
  Bot,
  Send,
  X,
  ChevronDown,
  Check,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { toast } from 'sonner';

const DocumentProcessor = ({ darkMode, setDarkMode, apiEndpoint }) => {
  const [documents, setDocuments] = useState([]);
  const [currentDocument, setCurrentDocument] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [summaryOptions, setSummaryOptions] = useState({
    type: 'medio',
    accuracy: 'standard'
  });
  const [schemaOptions, setSchemaOptions] = useState({
    type: 'brainstorming'
  });
  const [uploadProgress, setUploadProgress] = useState(0);

  // Load documents on component mount
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await axios.get(`${apiEndpoint}/documents`);
      setDocuments(response.data);
    } catch (error) {
      toast.error('Errore nel caricamento dei documenti');
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    // Check file size (100MB limit)
    if (file.size > 100 * 1024 * 1024) {
      toast.error('File troppo grande. Massimo 100MB.');
      return;
    }

    // Check file type
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Tipo di file non supportato. Usa PDF o immagini (JPG, PNG, WebP).');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${apiEndpoint}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        },
      });

      toast.success('Documento caricato e analizzato con successo!');
      loadDocuments();
      setCurrentDocument(response.data);
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Errore durante il caricamento';
      toast.error(errorMessage);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, [apiEndpoint]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.jpeg', '.jpg', '.png', '.webp']
    }
  });

  const generateSummary = async (documentId) => {
    setIsProcessing(true);
    try {
      const response = await axios.post(`${apiEndpoint}/generate-summary`, {
        document_id: documentId,
        summary_type: summaryOptions.type,
        accuracy_level: summaryOptions.accuracy
      });

      toast.success('Riassunto generato con successo!');
      loadDocuments();
      
      // Update current document if it matches
      if (currentDocument?.id === documentId) {
        const updatedDoc = await axios.get(`${apiEndpoint}/document/${documentId}`);
        setCurrentDocument(updatedDoc.data);
      }
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Errore nella generazione del riassunto';
      toast.error(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const generateSchema = async (documentId) => {
    setIsProcessing(true);
    try {
      const response = await axios.post(`${apiEndpoint}/generate-schema`, {
        document_id: documentId,
        schema_type: schemaOptions.type
      });

      toast.success('Schema generato con successo!');
      loadDocuments();
      
      // Update current document if it matches
      if (currentDocument?.id === documentId) {
        const updatedDoc = await axios.get(`${apiEndpoint}/document/${documentId}`);
        setCurrentDocument(updatedDoc.data);
      }
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Errore nella generazione dello schema';
      toast.error(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const exportPDF = async (documentId, contentType, filename) => {
    try {
      const response = await axios.get(`${apiEndpoint}/export-pdf/${documentId}?content_type=${contentType}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${filename}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('PDF esportato con successo!');
    } catch (error) {
      toast.error('Errore nell\'esportazione del PDF');
    }
  };

  const sendChatMessage = async () => {
    if (!chatInput.trim()) return;

    const userMessage = chatInput;
    setChatInput('');
    
    // Add user message to chat
    setChatMessages(prev => [...prev, { type: 'user', content: userMessage }]);
    
    try {
      const response = await axios.post(`${apiEndpoint}/chat`, {
        document_id: currentDocument?.id,
        message: userMessage,
        context: currentDocument?.extracted_text
      });

      // Add AI response to chat
      setChatMessages(prev => [...prev, { type: 'ai', content: response.data.response }]);
    } catch (error) {
      toast.error('Errore nella chat');
      setChatMessages(prev => [...prev, { type: 'error', content: 'Errore nella comunicazione con l\'AI' }]);
    }
  };

  const selectDocument = async (docId) => {
    try {
      const response = await axios.get(`${apiEndpoint}/document/${docId}`);
      setCurrentDocument(response.data);
      setChatMessages([]); // Clear chat when switching documents
    } catch (error) {
      toast.error('Errore nel caricamento del documento');
    }
  };

  const deleteDocument = async (documentId, filename, e) => {
    // Blocca la propagazione per evitare che venga chiamato selectDocument
    e.stopPropagation();

    if (!window.confirm(`Sei sicuro di voler eliminare il documento "${filename}"?`)) {
        return;
    }

    try {
        await axios.delete(`${apiEndpoint}/document/${documentId}`);

        toast.success(`Documento "${filename}" eliminato con successo.`);
        
        // 1. Aggiorna la lista dei documenti
        loadDocuments();

        // 2. Se stiamo visualizzando il documento eliminato, chiudi la visualizzazione
        if (currentDocument?.id === documentId) {
            setCurrentDocument(null);
        }

    } catch (error) {
        const errorMessage = error.response?.data?.detail || 'Errore durante l\'eliminazione del documento';
        toast.error(errorMessage);
    }
};

  return (
    <div className="min-h-screen p-4 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-gradient-to-br from-orange-500 to-amber-600 rounded-xl text-white">
            <Brain className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-amber-600 bg-clip-text text-transparent">
              DocBrains
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">Analisi Documenti con AI</p>
          </div>
        </div>
        
        <Button
          onClick={() => setDarkMode(!darkMode)}
          variant="ghost"
          size="icon"
          className="rounded-full"
          data-testid="dark-mode-toggle"
        >
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sidebar - Document List */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="document-card" data-testid="documents-sidebar">
            <CardHeader>
              <CardTitle className="text-lg flex items-center space-x-2">
                <FileText className="w-5 h-5" />
                <span>I tuoi documenti</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {documents.length === 0 ? (
                <p className="text-sm text-zinc-600 dark:text-zinc-400 text-center py-4">
                  Nessun documento caricato
                </p>
              ) : (
                documents.map((doc) => (
                  <div 
                    key={doc.id} 
                    className={`p-3 rounded-lg border-2 cursor-pointer transition-all duration-200 ${
                      currentDocument?.id === doc.id 
                        ? 'border-orange-500 bg-orange-50 dark:bg-orange-950/20' 
                        : 'border-zinc-200 dark:border-zinc-700 hover:border-orange-300 dark:hover:border-orange-600'
                    }`}
                    onClick={() => selectDocument(doc.id)}
                    data-testid={`document-item-${doc.id}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium text-sm truncate">{doc.filename}</h3>
                      <div className="flex space-x-1">
                        {doc.has_summary && (
                          <Badge variant="secondary" className="text-xs">
                            <Sparkles className="w-3 h-3 mr-1" />R
                          </Badge>
                        )}
                        {doc.has_schema && (
                          <Badge variant="secondary" className="text-xs">
                            <Network className="w-3 h-3 mr-1" />S
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-zinc-600 dark:text-zinc-400">
                        {(doc.file_size / 1024 / 1024).toFixed(1)} MB
                      </p>
                      <Button
                        onClick={(e) => deleteDocument(doc.id, doc.filename, e)}
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-red-500 hover:text-red-700 dark:hover:text-red-400"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-9 space-y-6">
          {/* Upload Area */}
          {!currentDocument && (
            <Card className="document-card" data-testid="upload-area">
              <CardContent className="pt-6">
                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer ${
                    isDragActive 
                      ? 'border-orange-500 bg-orange-50 dark:bg-orange-950/20' 
                      : 'border-zinc-300 dark:border-zinc-600 hover:border-orange-400 dark:hover:border-orange-500'
                  }`}
                >
                  <input {...getInputProps()} />
                  
                  {isUploading ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-center">
                        <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
                      </div>
                      <div className="space-y-2">
                        <p className="text-lg font-medium">Caricamento in corso...</p>
                        <Progress value={uploadProgress} className="w-full max-w-xs mx-auto" />
                        <p className="text-sm text-zinc-600 dark:text-zinc-400">{uploadProgress}%</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-center">
                        <div className="p-4 bg-gradient-to-br from-orange-500 to-amber-600 rounded-full text-white">
                          <Upload className="w-12 h-12" />
                        </div>
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">
                          {isDragActive ? 'Rilascia il file qui' : 'Carica il tuo documento'}
                        </h3>
                        <p className="text-zinc-600 dark:text-zinc-400 mb-4">
                          Trascina un file PDF o un'immagine, oppure clicca per selezionare
                        </p>
                        <div className="flex items-center justify-center space-x-4 text-sm text-zinc-500 dark:text-zinc-500">
                          <span>PDF</span>
                          <span>•</span>
                          <span>JPG</span>
                          <span>•</span>
                          <span>PNG</span>
                          <span>•</span>
                          <span>Max 100MB</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Document Content */}
          {currentDocument && (
            <Card className="document-card" data-testid="document-content">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xl">{currentDocument.filename}</CardTitle>
                  <Button
                    onClick={() => setCurrentDocument(null)}
                    variant="ghost"
                    size="icon"
                    data-testid="close-document"
                  >
                    <X className="w-5 h-5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="content" className="w-full">
                  <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="content" data-testid="content-tab">
                      <FileSearch className="w-4 h-4 mr-2" />
                      Contenuto
                    </TabsTrigger>
                    <TabsTrigger value="summary" data-testid="summary-tab">
                      <BookOpen className="w-4 h-4 mr-2" />
                      Riassunto
                    </TabsTrigger>
                    <TabsTrigger value="schema" data-testid="schema-tab">
                      <Network className="w-4 h-4 mr-2" />
                      Schema
                    </TabsTrigger>
                    <TabsTrigger value="export" data-testid="export-tab">
                      <Download className="w-4 h-4 mr-2" />
                      Export
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="content" className="mt-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">Testo estratto</h3>
                        <Badge variant="outline">
                          {currentDocument.extracted_text?.length || 0} caratteri
                        </Badge>
                      </div>
                      <div className="max-h-96 overflow-y-auto p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border prose prose-sm max-w-none">
                        <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                          {currentDocument.extracted_text || 'Nessun testo disponibile'}
                        </pre>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="summary" className="mt-6">
                    <div className="space-y-6">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">Riassunto del documento</h3>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm" data-testid="summary-settings">
                              <Settings className="w-4 h-4 mr-2" />
                              Impostazioni
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Impostazioni Riassunto</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4">
                              <div>
                                <label className="block text-sm font-medium mb-2">Lunghezza</label>
                                <Select value={summaryOptions.type} onValueChange={(value) => setSummaryOptions(prev => ({...prev, type: value}))}>
                                  <SelectTrigger data-testid="summary-length-select">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="breve">Breve (200 parole)</SelectItem>
                                    <SelectItem value="medio">Medio (300-500 parole)</SelectItem>
                                    <SelectItem value="dettagliato">Dettagliato (600-800 parole)</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              <div>
                                <label className="block text-sm font-medium mb-2">Accuratezza</label>
                                <Select value={summaryOptions.accuracy} onValueChange={(value) => setSummaryOptions(prev => ({...prev, accuracy: value}))}>
                                  <SelectTrigger data-testid="summary-accuracy-select">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="standard">Standard</SelectItem>
                                    <SelectItem value="alta">Alta precisione</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>
                      </div>

                      {currentDocument.summary_text ? (
                        <div className="space-y-4">
                          <div className="flex items-center space-x-2">
                            <Check className="w-5 h-5 text-green-600" />
                            <span className="text-sm text-green-600 dark:text-green-400">
                              Riassunto generato ({currentDocument.summary_type})
                            </span>
                          </div>
                          <div className="max-h-96 overflow-y-auto p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border prose max-w-none">
                            <div className="whitespace-pre-wrap text-sm leading-relaxed">
                              {currentDocument.summary_text}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-8">
                          <div className="mb-4">
                            <Sparkles className="w-12 h-12 mx-auto text-zinc-400" />
                          </div>
                          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
                            Nessun riassunto generato per questo documento
                          </p>
                          <Button 
                            onClick={() => generateSummary(currentDocument.id)}
                            disabled={isProcessing}
                            className="btn-primary"
                            data-testid="generate-summary-btn"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <Sparkles className="w-4 h-4 mr-2" />
                            )}
                            Genera Riassunto
                          </Button>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="schema" className="mt-6">
                    <div className="space-y-6">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">Schema del documento</h3>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm" data-testid="schema-settings">
                              <Settings className="w-4 h-4 mr-2" />
                              Impostazioni
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Impostazioni Schema</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4">
                              <div>
                                <label className="block text-sm font-medium mb-2">Tipo di schema</label>
                                <Select value={schemaOptions.type} onValueChange={(value) => setSchemaOptions(prev => ({...prev, type: value}))}>
                                  <SelectTrigger data-testid="schema-type-select">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="brainstorming">Brainstorming / Mappa Mentale</SelectItem>
                                    <SelectItem value="cascata">Schema a Cascata / Flow Chart</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>
                      </div>

                      {currentDocument.mindmap_schema ? (
                        <div className="space-y-4">
                          <div className="flex items-center space-x-2">
                            <Check className="w-5 h-5 text-green-600" />
                            <span className="text-sm text-green-600 dark:text-green-400">
                              Schema generato ({currentDocument.schema_type})
                            </span>
                          </div>
                          <div className="max-h-96 overflow-y-auto p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border">
                            <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                              {currentDocument.mindmap_schema}
                            </pre>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-8">
                          <div className="mb-4">
                            <Network className="w-12 h-12 mx-auto text-zinc-400" />
                          </div>
                          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
                            Nessuno schema generato per questo documento
                          </p>
                          <Button 
                            onClick={() => generateSchema(currentDocument.id)}
                            disabled={isProcessing}
                            className="btn-primary"
                            data-testid="generate-schema-btn"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <Network className="w-4 h-4 mr-2" />
                            )}
                            Genera Schema
                          </Button>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="export" className="mt-6">
                    <div className="space-y-6">
                      <h3 className="text-lg font-semibold">Esporta contenuti</h3>
                      <div className="grid gap-4">
                        <div className="p-4 border rounded-lg">
                          <div className="flex items-center justify-between">
                            <div>
                              <h4 className="font-medium">Testo completo</h4>
                              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                                Esporta tutto il testo estratto dal documento
                              </p>
                            </div>
                            <Button
                              onClick={() => exportPDF(currentDocument.id, 'full', `${currentDocument.filename}_completo`)}
                              variant="outline"
                              data-testid="export-full-text"
                            >
                              <Download className="w-4 h-4 mr-2" />
                              PDF
                            </Button>
                          </div>
                        </div>
                        
                        {currentDocument.summary_text && (
                          <div className="p-4 border rounded-lg">
                            <div className="flex items-center justify-between">
                              <div>
                                <h4 className="font-medium">Riassunto</h4>
                                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                                  Esporta il riassunto generato
                                </p>
                              </div>
                              <Button
                                onClick={() => exportPDF(currentDocument.id, 'summary', `${currentDocument.filename}_riassunto`)}
                                variant="outline"
                                data-testid="export-summary"
                              >
                                <Download className="w-4 h-4 mr-2" />
                                PDF
                              </Button>
                            </div>
                          </div>
                        )}
                        
                        {currentDocument.mindmap_schema && (
                          <div className="p-4 border rounded-lg">
                            <div className="flex items-center justify-between">
                              <div>
                                <h4 className="font-medium">Schema</h4>
                                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                                  Esporta lo schema generato
                                </p>
                              </div>
                              <Button
                                onClick={() => exportPDF(currentDocument.id, 'schema', `${currentDocument.filename}_schema`)}
                                variant="outline"
                                data-testid="export-schema"
                              >
                                <Download className="w-4 h-4 mr-2" />
                                PDF
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Chat Bot */}
      <div className="fixed bottom-6 right-6 z-[9999]">
        {isChatOpen ? (
          <Card className="w-80 h-96 shadow-2xl" data-testid="chat-widget">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Bot className="w-5 h-5 text-orange-500" />
                  <CardTitle className="text-sm">Assistente AI</CardTitle>
                </div>
                <Button
                  onClick={() => setIsChatOpen(false)}
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  data-testid="close-chat"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex flex-col h-80">
              <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="chat-messages">
                {chatMessages.length === 0 ? (
                  <div className="text-center py-8">
                    <Bot className="w-8 h-8 mx-auto text-zinc-400 mb-2" />
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      Ciao! Come posso aiutarti con il documento?
                    </p>
                  </div>
                ) : (
                  chatMessages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xs px-3 py-2 rounded-lg text-sm ${
                        msg.type === 'user' 
                          ? 'bg-orange-500 text-white' 
                          : msg.type === 'error'
                          ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
                          : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="p-4 border-t">
                <div className="flex space-x-2">
                  <Textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Scrivi un messaggio..."
                    className="flex-1 resize-none h-9"
                    onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendChatMessage())}
                    data-testid="chat-input"
                  />
                  <Button
                    onClick={sendChatMessage}
                    size="icon"
                    className="h-9 w-9"
                    disabled={!chatInput.trim()}
                    data-testid="send-message"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Button
            onClick={() => setIsChatOpen(true)}
            className="rounded-full h-14 w-14 shadow-lg bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700"
            data-testid="open-chat"
          >
            <MessageCircle className="w-6 h-6" />
          </Button>
        )}
      </div>
    </div>
  );
};

export default DocumentProcessor;