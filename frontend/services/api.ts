import { ApiResponse } from '../types';

const API_URL = 'http://localhost:5000/api/analyze/bank/statement';

export const uploadBankStatement = async (file: File): Promise<ApiResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    let response: Response;

    // 1. Attempt the network request
    try {
      response = await fetch(API_URL, {
        method: 'POST',
        body: formData,
      });
    } catch (networkError) {
      // This catches DNS errors, connection refused, or CORS issues
      console.error('Network request failed:', networkError);
      throw new Error('Network Error: Unable to connect to the backend server. Please ensure the API is running at localhost:5000.');
    }

    // 2. Handle HTTP Errors (4xx, 5xx)
    if (!response.ok) {
      let errorMsg = `Upload failed with status ${response.status}`;
      
      try {
        const errorData = await response.json();
        
        // Check for specific deep-nested error from backend logic (e.g., missing python dependency)
        if (errorData?.result?.error) {
          errorMsg = errorData.result.error;
        } 
        // Check for standard API message
        else if (errorData?.message) {
          errorMsg = errorData.message;
        }
        // Fallback for generic details
        else if (errorData?.detail) {
           errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch (parseError) {
        // Response was not JSON (e.g., raw 500 HTML page or Nginx error)
        if (response.statusText) {
          errorMsg = `Server Error: ${response.status} ${response.statusText}`;
        }
      }
      
      throw new Error(errorMsg);
    }

    // 3. Parse success response
    const data: ApiResponse = await response.json();
    return data;

  } catch (error) {
    // Propagate the specific error message to the UI
    throw error;
  }
};