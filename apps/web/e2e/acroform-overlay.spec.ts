/**
 * E2E tests for AcroForm field overlay functionality.
 *
 * These tests investigate why the AcroForm field overlay is not displaying
 * in the Documents tab of the job detail page.
 *
 * Evidence collection:
 * - Screenshots at each step
 * - Network request/response capture for /acroform-fields endpoint
 * - DOM inspection for overlay elements
 * - Console log capture
 */

import { test, expect, type Page, type Response } from '@playwright/test';
import * as path from 'path';
import { fileURLToPath } from 'url';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SCREENSHOT_DIR = path.resolve(__dirname, '../e2e-screenshots');
const TEST_PDF_PATH = path.resolve(__dirname, '../../tests/assets/2025bun_01_input.pdf');

interface AcroFormNetworkData {
  request: {
    url: string;
    method: string;
  } | null;
  response: {
    status: number;
    body: unknown;
  } | null;
  error: string | null;
}

interface OverlayDomInfo {
  fieldOverlayExists: boolean;
  fieldOverlayStyle: string | null;
  fieldRectangles: Array<{
    style: string;
    title: string | null;
  }>;
  pageViewerExists: boolean;
  imageContainerExists: boolean;
  imageLoaded: boolean;
  imageDimensions: { width: number; height: number } | null;
}

// Ensure screenshot directory exists
test.beforeAll(async () => {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
});

/**
 * Helper to capture screenshot with descriptive name
 */
async function captureScreenshot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${name}.png`,
    fullPage: false,
  });
}

/**
 * Helper to capture full page screenshot
 */
async function captureFullPageScreenshot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${name}-fullpage.png`,
    fullPage: true,
  });
}

/**
 * Helper to setup network monitoring for acroform-fields endpoint
 */
function setupAcroFormNetworkMonitor(page: Page): {
  getData: () => AcroFormNetworkData;
  waitForRequest: () => Promise<void>;
} {
  const data: AcroFormNetworkData = {
    request: null,
    response: null,
    error: null,
  };

  let resolveRequestPromise: (() => void) | null = null;
  const requestPromise = new Promise<void>((resolve) => {
    resolveRequestPromise = resolve;
    // Auto-resolve after timeout if no request comes
    setTimeout(resolve, 10000);
  });

  page.on('request', (request) => {
    if (request.url().includes('acroform-fields')) {
      data.request = {
        url: request.url(),
        method: request.method(),
      };
    }
  });

  page.on('response', async (response) => {
    if (response.url().includes('acroform-fields')) {
      try {
        const body = await response.json();
        data.response = {
          status: response.status(),
          body,
        };
      } catch (e) {
        data.response = {
          status: response.status(),
          body: null,
        };
        data.error = `Failed to parse response: ${e}`;
      }
      if (resolveRequestPromise) {
        resolveRequestPromise();
      }
    }
  });

  page.on('requestfailed', (request) => {
    if (request.url().includes('acroform-fields')) {
      data.error = request.failure()?.errorText || 'Unknown request failure';
      if (resolveRequestPromise) {
        resolveRequestPromise();
      }
    }
  });

  return {
    getData: () => data,
    waitForRequest: () => requestPromise,
  };
}

/**
 * Helper to inspect overlay DOM elements
 */
async function inspectOverlayDom(page: Page): Promise<OverlayDomInfo> {
  return await page.evaluate(() => {
    // Find the field overlay container
    const overlayContainers = document.querySelectorAll('[style*="position: absolute"]');
    let fieldOverlay: Element | null = null;

    // Look for the overlay with pointer-events: none (characteristic of FieldOverlay)
    overlayContainers.forEach((el) => {
      const style = (el as HTMLElement).style;
      if (
        style.position === 'absolute' &&
        style.pointerEvents === 'none' &&
        style.top === '0px' &&
        style.left === '0px'
      ) {
        fieldOverlay = el;
      }
    });

    // Find field rectangles (children of overlay with pointer-events: auto)
    const fieldRectangles: Array<{ style: string; title: string | null }> = [];
    if (fieldOverlay) {
      fieldOverlay.querySelectorAll('[style*="pointer-events: auto"]').forEach((el) => {
        fieldRectangles.push({
          style: (el as HTMLElement).getAttribute('style') || '',
          title: el.getAttribute('title'),
        });
      });
    }

    // Check for PageViewer image
    const pageViewerImg = document.querySelector('img[alt*="Page"]') as HTMLImageElement | null;
    const imageContainer = pageViewerImg?.parentElement;

    return {
      fieldOverlayExists: fieldOverlay !== null,
      fieldOverlayStyle: fieldOverlay
        ? (fieldOverlay as HTMLElement).getAttribute('style')
        : null,
      fieldRectangles,
      pageViewerExists: !!pageViewerImg,
      imageContainerExists: !!imageContainer,
      imageLoaded: pageViewerImg?.complete ?? false,
      imageDimensions: pageViewerImg
        ? { width: pageViewerImg.offsetWidth, height: pageViewerImg.offsetHeight }
        : null,
    };
  });
}

/**
 * Helper to get console logs
 */
function setupConsoleLogCapture(page: Page): { getLogs: () => string[] } {
  const logs: string[] = [];

  page.on('console', (msg) => {
    logs.push(`[${msg.type()}] ${msg.text()}`);
  });

  return { getLogs: () => logs };
}

/**
 * Helper to write evidence to JSON file
 */
function writeEvidence(filename: string, data: unknown): void {
  fs.writeFileSync(
    path.join(SCREENSHOT_DIR, filename),
    JSON.stringify(data, null, 2)
  );
}

test.describe('AcroForm Field Overlay - Full Flow', () => {
  test('should create job, navigate to Documents tab, and verify overlay', async ({ page }) => {
    // Setup monitoring
    const networkMonitor = setupAcroFormNetworkMonitor(page);
    const consoleCapture = setupConsoleLogCapture(page);

    // Step 1: Navigate to home page
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await captureScreenshot(page, '01-home-page');

    // Step 2: Wait for API health check
    await expect(page.getByText('API Connected')).toBeVisible({ timeout: 10000 });
    await captureScreenshot(page, '02-api-connected');

    // Step 3: Click "Create New Job"
    await page.getByRole('button', { name: 'Create New Job' }).click();
    await page.waitForLoadState('networkidle');
    await captureScreenshot(page, '03-job-create-page');

    // Step 4: Select "Scratch Mode" (doesn't require source document)
    await page.getByText('Scratch Mode').click();
    await captureScreenshot(page, '04-scratch-mode-selected');

    // Step 5: Upload target document
    // The DocumentUploader has a hidden file input - we need to set files on it
    // then click the "Upload" button that appears after file selection
    const fileInputs = page.locator('input[type="file"]');
    const fileInputCount = await fileInputs.count();
    console.log(`Found ${fileInputCount} file inputs`);

    // Upload to the first (and should be only in scratch mode) file input
    if (fileInputCount > 0) {
      await fileInputs.first().setInputFiles(TEST_PDF_PATH);
      // Wait for file to be selected
      await page.waitForTimeout(1000);
      await captureScreenshot(page, '05a-file-selected');

      // Click the Upload button that appears after file selection
      const uploadButton = page.getByRole('button', { name: 'Upload', exact: true });
      if (await uploadButton.isVisible()) {
        await uploadButton.click();
        // Wait for upload API call to complete
        await page.waitForTimeout(5000);
        await captureScreenshot(page, '05b-target-uploaded');
      }
    }

    // Step 6: Click "Create Job"
    // Wait for the button to become enabled (document must be uploaded)
    const createJobButton = page.getByRole('button', { name: 'Create Job' });
    await expect(createJobButton).toBeEnabled({ timeout: 10000 });
    await createJobButton.click();
    await page.waitForLoadState('networkidle');
    // Wait for job creation and navigation
    await page.waitForTimeout(5000);
    await captureScreenshot(page, '06-job-created');

    // Step 7: Check if we're on job detail page (look for tabs)
    const documentsTab = page.getByRole('button', { name: /Documents/ });
    const hasDocumentsTab = await documentsTab.isVisible();

    if (!hasDocumentsTab) {
      console.log('Documents tab not visible - may not be on job detail page');
      await captureFullPageScreenshot(page, '06b-not-on-job-page');

      // Log page content for debugging
      const pageContent = await page.content();
      writeEvidence('page-content.html', pageContent);
    }

    // Step 8: Click Documents tab
    if (hasDocumentsTab) {
      await captureScreenshot(page, '07-before-documents-click');
      await documentsTab.click();
      await page.waitForLoadState('networkidle');

      // Wait for potential acroform-fields request
      console.log('Waiting for AcroForm fields API request...');
      await networkMonitor.waitForRequest();

      await page.waitForTimeout(3000);
      await captureScreenshot(page, '08-documents-tab-active');
    }

    // Step 9: Inspect DOM for overlay elements
    const domInfo = await inspectOverlayDom(page);

    // Step 10: Capture final evidence
    await captureFullPageScreenshot(page, '09-final-state');

    // Capture the preview area specifically if visible
    const previewCard = page.locator('text=Target:').locator('..');
    if (await previewCard.isVisible()) {
      await previewCard.screenshot({ path: `${SCREENSHOT_DIR}/10-target-preview.png` });
    }

    // Collect all evidence
    const evidence = {
      timestamp: new Date().toISOString(),
      networkData: networkMonitor.getData(),
      domInfo,
      consoleLogs: consoleCapture.getLogs(),
      url: page.url(),
    };

    writeEvidence('full-flow-evidence.json', evidence);

    // Log evidence for test output
    console.log('\n=== AcroForm Overlay Investigation Evidence ===\n');
    console.log('Network Data:', JSON.stringify(evidence.networkData, null, 2));
    console.log('\nDOM Info:', JSON.stringify(evidence.domInfo, null, 2));
    console.log('\nConsole Logs (last 20):', evidence.consoleLogs.slice(-20).join('\n'));
    console.log('\nFinal URL:', evidence.url);

    // Analysis and assertions
    console.log('\n=== Analysis ===\n');

    if (evidence.networkData.request) {
      console.log('[OK] AcroForm fields API was called:', evidence.networkData.request.url);
      if (evidence.networkData.response) {
        console.log('[OK] API responded with status:', evidence.networkData.response.status);
        const body = evidence.networkData.response.body as Record<string, unknown> | null;
        if (body) {
          console.log('[INFO] Response has_acroform:', (body as { data?: { has_acroform?: boolean } }).data?.has_acroform);
          console.log('[INFO] Response fields count:', ((body as { data?: { fields?: unknown[] } }).data?.fields as unknown[] | undefined)?.length ?? 'N/A');
        }
      }
    } else {
      console.log('[ISSUE] AcroForm fields API was NOT called');
    }

    if (evidence.domInfo.pageViewerExists) {
      console.log('[OK] PageViewer image exists');
    } else {
      console.log('[ISSUE] PageViewer image NOT found');
    }

    if (evidence.domInfo.imageLoaded) {
      console.log('[OK] Image is loaded');
      console.log('[INFO] Image dimensions:', evidence.domInfo.imageDimensions);
    } else {
      console.log('[ISSUE] Image is NOT loaded');
    }

    if (evidence.domInfo.fieldOverlayExists) {
      console.log('[OK] FieldOverlay container exists');
      console.log('[INFO] Overlay style:', evidence.domInfo.fieldOverlayStyle);
    } else {
      console.log('[ISSUE] FieldOverlay container NOT found');
    }

    if (evidence.domInfo.fieldRectangles.length > 0) {
      console.log(`[OK] Found ${evidence.domInfo.fieldRectangles.length} field rectangles`);
      evidence.domInfo.fieldRectangles.slice(0, 3).forEach((rect, i) => {
        console.log(`  Rectangle ${i + 1}: title="${rect.title}"`);
      });
    } else {
      console.log('[ISSUE] No field rectangles found');
    }
  });

  test('should verify PageViewer component state after image loads', async ({ page }) => {
    // This test focuses specifically on the PageViewer internal state
    const networkMonitor = setupAcroFormNetworkMonitor(page);

    // Go through the flow to get to Documents tab
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Create job in scratch mode
    await page.getByRole('button', { name: 'Create New Job' }).click();
    await page.getByText('Scratch Mode').click();

    // Upload target document
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(TEST_PDF_PATH);
    await page.waitForTimeout(1000);

    // Click Upload button
    const uploadButton = page.getByRole('button', { name: 'Upload', exact: true });
    if (await uploadButton.isVisible()) {
      await uploadButton.click();
      await page.waitForTimeout(5000);
    }

    // Create job
    const createJobButton = page.getByRole('button', { name: 'Create Job' });
    await expect(createJobButton).toBeEnabled({ timeout: 10000 });
    await createJobButton.click();
    await page.waitForTimeout(5000);

    // Go to Documents tab
    const documentsTab = page.getByRole('button', { name: /Documents/ });
    if (await documentsTab.isVisible()) {
      await documentsTab.click();
      await page.waitForTimeout(3000);
    }

    await captureScreenshot(page, 'pageviewer-state-01');

    // Wait for image to load
    const pageImage = page.locator('img[alt*="Page"]').first();
    if (await pageImage.isVisible()) {
      await expect(pageImage).toBeVisible();

      // Wait for image complete event
      await page.waitForFunction(() => {
        const img = document.querySelector('img[alt*="Page"]') as HTMLImageElement;
        return img && img.complete && img.naturalHeight > 0;
      }, { timeout: 10000 });

      await captureScreenshot(page, 'pageviewer-state-02-image-loaded');
    }

    // Check the state after image loads
    const stateInfo = await page.evaluate(() => {
      const img = document.querySelector('img[alt*="Page"]') as HTMLImageElement | null;
      if (!img) return { imageFound: false };

      // Get parent container (the one with position: relative)
      const imageContainer = img.parentElement;

      // Count all children of the image container
      const children = imageContainer?.children ?? [];
      const childInfo: Array<{ tagName: string; style: string; hasChildren: boolean }> = [];
      for (let i = 0; i < children.length; i++) {
        const child = children[i] as HTMLElement;
        childInfo.push({
          tagName: child.tagName,
          style: child.style.cssText || child.getAttribute('style') || 'no style',
          hasChildren: child.children.length > 0,
        });
      }

      return {
        imageFound: true,
        imageComplete: img.complete,
        imageNaturalSize: { width: img.naturalWidth, height: img.naturalHeight },
        imageDisplaySize: { width: img.offsetWidth, height: img.offsetHeight },
        containerPosition: imageContainer ? window.getComputedStyle(imageContainer).position : 'N/A',
        containerChildCount: children.length,
        childInfo,
      };
    });

    console.log('\n=== PageViewer State ===\n');
    console.log(JSON.stringify(stateInfo, null, 2));
    writeEvidence('pageviewer-state.json', stateInfo);

    // Check network monitor
    await networkMonitor.waitForRequest();
    const networkData = networkMonitor.getData();
    console.log('\nNetwork Data:', JSON.stringify(networkData, null, 2));
    writeEvidence('pageviewer-network.json', networkData);

    await captureScreenshot(page, 'pageviewer-state-03-final');
  });
});

test.describe('AcroForm API Direct Test', () => {
  test('should capture detailed API response for acroform-fields', async ({ page, request }) => {
    // First create a job to get a document ID
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Track document IDs from network requests
    let documentId: string | null = null;

    page.on('response', async (response) => {
      if (response.url().includes('/documents') && response.status() === 200) {
        try {
          const body = await response.json();
          if (body.data?.document_id) {
            documentId = body.data.document_id;
            console.log('Captured document ID:', documentId);
          }
        } catch {
          // Ignore parse errors
        }
      }
    });

    // Create job in scratch mode
    await page.getByRole('button', { name: 'Create New Job' }).click();
    await page.getByText('Scratch Mode').click();

    // Upload target document
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(TEST_PDF_PATH);
    await page.waitForTimeout(1000);

    // Click Upload button
    const uploadButton = page.getByRole('button', { name: 'Upload', exact: true });
    if (await uploadButton.isVisible()) {
      await uploadButton.click();
      await page.waitForTimeout(5000);
    }

    await captureScreenshot(page, 'api-test-01-uploaded');

    // Wait a bit more to ensure document ID is captured
    await page.waitForTimeout(2000);

    if (documentId) {
      // Call the API directly
      console.log('\n=== Direct API Call ===\n');
      console.log('Document ID:', documentId);

      const apiBaseUrl = 'http://localhost:8000';
      const apiUrl = `${apiBaseUrl}/api/v1/documents/${documentId}/acroform-fields`;

      try {
        const response = await request.get(apiUrl);
        const status = response.status();
        console.log('Status:', status);

        if (status === 200) {
          const body = await response.json();
          console.log('Response Body:', JSON.stringify(body, null, 2));
          writeEvidence('api-direct-response.json', { documentId, status, body });

          // Analyze the response
          const data = body.data;
          if (data) {
            console.log('\n=== API Response Analysis ===');
            console.log('has_acroform:', data.has_acroform);
            console.log('preview_scale:', data.preview_scale);
            console.log('page_dimensions:', data.page_dimensions);
            console.log('fields count:', data.fields?.length ?? 0);

            if (data.fields && data.fields.length > 0) {
              console.log('\nFirst 3 fields:');
              data.fields.slice(0, 3).forEach((field: Record<string, unknown>, i: number) => {
                console.log(`  Field ${i + 1}:`, JSON.stringify(field, null, 2));
              });
            }
          }
        } else {
          const text = await response.text();
          console.log('Error response:', text);
          writeEvidence('api-direct-error.json', { documentId, status, error: text });
        }
      } catch (e) {
        console.log('API call failed:', e);
        writeEvidence('api-direct-exception.json', { documentId, error: String(e) });
      }
    } else {
      console.log('Could not capture document ID from network requests');
    }

    await captureScreenshot(page, 'api-test-02-final');
  });
});

test.describe('AcroForm Overlay Rendering Conditions', () => {
  test('should check all conditions required for overlay to render', async ({ page }) => {
    /**
     * Based on PageViewer.tsx, FieldOverlay renders when ALL of these are true:
     * 1. !loading && !error && imageUrl
     * 2. showFieldOverlay === true (passed from JobDetailPage)
     * 3. acroFormData !== null
     * 4. acroFormData.has_acroform === true
     * 5. imageDimensions !== null (set after image onLoad)
     *
     * And FieldOverlay returns null if pageFields.length === 0
     */

    const networkMonitor = setupAcroFormNetworkMonitor(page);

    // Go through the flow
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: 'Create New Job' }).click();
    await page.getByText('Scratch Mode').click();

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(TEST_PDF_PATH);
    await page.waitForTimeout(1000);

    // Click Upload button
    const uploadButton = page.getByRole('button', { name: 'Upload', exact: true });
    if (await uploadButton.isVisible()) {
      await uploadButton.click();
      await page.waitForTimeout(5000);
    }

    const createJobButton = page.getByRole('button', { name: 'Create Job' });
    await expect(createJobButton).toBeEnabled({ timeout: 10000 });
    await createJobButton.click();
    await page.waitForTimeout(5000);

    const documentsTab = page.getByRole('button', { name: /Documents/ });
    if (await documentsTab.isVisible()) {
      await documentsTab.click();
      await page.waitForTimeout(5000);
    }

    await captureScreenshot(page, 'conditions-check-01');

    // Check each condition
    const conditions = await page.evaluate(() => {
      const result = {
        // Condition 1: Image state
        imageUrl: false,
        imageLoading: false,
        imageError: false,

        // Condition 2: showFieldOverlay (can't directly check prop, but we can infer)
        // If we're on Documents tab and PageViewer is rendered, it should be true

        // Condition 3 & 4: acroFormData (inferred from DOM)
        acroFormDataLoaded: false,
        hasAcroform: false,

        // Condition 5: imageDimensions
        imageDimensionsSet: false,
        imageDimensions: null as { width: number; height: number } | null,

        // Condition 6: pageFields.length > 0
        overlayRendered: false,
        fieldRectanglesCount: 0,

        // Additional debug info
        viewportChildren: [] as string[],
        imageContainerChildren: [] as string[],
      };

      // Find the image
      const img = document.querySelector('img[alt*="Page"]') as HTMLImageElement | null;
      if (img) {
        result.imageUrl = !!img.src;
        result.imageLoading = !img.complete;
        result.imageDimensionsSet = img.offsetWidth > 0 && img.offsetHeight > 0;
        result.imageDimensions = {
          width: img.offsetWidth,
          height: img.offsetHeight,
        };

        // Check image container for overlay
        const container = img.parentElement;
        if (container) {
          for (let i = 0; i < container.children.length; i++) {
            const child = container.children[i] as HTMLElement;
            result.imageContainerChildren.push(
              `${child.tagName} - ${child.style.cssText.substring(0, 100)}`
            );

            // Check if this is the overlay container
            if (
              child.style.position === 'absolute' &&
              child.style.pointerEvents === 'none'
            ) {
              result.overlayRendered = true;
              result.fieldRectanglesCount = child.children.length;

              // If overlay exists with children, acroFormData must have loaded with fields
              if (child.children.length > 0) {
                result.acroFormDataLoaded = true;
                result.hasAcroform = true;
              }
            }
          }
        }
      }

      // Check viewport area
      const viewport = document.querySelector('[style*="overflow: auto"]');
      if (viewport) {
        for (let i = 0; i < viewport.children.length; i++) {
          result.viewportChildren.push((viewport.children[i] as HTMLElement).tagName);
        }
      }

      return result;
    });

    console.log('\n=== Overlay Rendering Conditions ===\n');
    console.log(JSON.stringify(conditions, null, 2));

    // Get network data for acroform-fields
    await networkMonitor.waitForRequest();
    const networkData = networkMonitor.getData();

    // Analyze network response
    let apiHasAcroform = false;
    let apiFieldsCount = 0;
    if (networkData.response?.body) {
      const body = networkData.response.body as { data?: { has_acroform?: boolean; fields?: unknown[] } };
      apiHasAcroform = body.data?.has_acroform ?? false;
      apiFieldsCount = body.data?.fields?.length ?? 0;
    }

    const analysis = {
      conditions,
      networkData,
      apiAnalysis: {
        hasAcroform: apiHasAcroform,
        fieldsCount: apiFieldsCount,
      },
    };

    writeEvidence('conditions-analysis.json', analysis);

    console.log('\n=== Analysis Summary ===\n');
    console.log('Image loaded:', conditions.imageUrl && !conditions.imageLoading);
    console.log('Image dimensions set:', conditions.imageDimensionsSet);
    console.log('API called:', !!networkData.request);
    console.log('API has_acroform:', apiHasAcroform);
    console.log('API fields count:', apiFieldsCount);
    console.log('Overlay rendered:', conditions.overlayRendered);
    console.log('Field rectangles:', conditions.fieldRectanglesCount);

    // Root cause identification
    console.log('\n=== Potential Root Causes ===\n');
    if (!networkData.request) {
      console.log('- [CRITICAL] AcroForm API was never called');
      console.log('  Check: Is showFieldOverlay prop being passed to PageViewer?');
    } else if (!apiHasAcroform) {
      console.log('- [CRITICAL] API returned has_acroform: false');
      console.log('  Check: Does the PDF actually have AcroForm fields?');
    } else if (apiFieldsCount === 0) {
      console.log('- [CRITICAL] API returned empty fields array');
      console.log('  Check: Are fields being extracted correctly by the backend?');
    } else if (!conditions.imageDimensionsSet) {
      console.log('- [ISSUE] Image dimensions not set');
      console.log('  Check: Is the image onLoad event firing correctly?');
    } else if (!conditions.overlayRendered) {
      console.log('- [ISSUE] Overlay not rendered despite all conditions met');
      console.log('  Check: React re-render timing, acroFormData state update');
    } else if (conditions.fieldRectanglesCount === 0) {
      console.log('- [ISSUE] Overlay exists but no field rectangles');
      console.log('  Check: pageFields filter for current page, field bbox data');
    } else {
      console.log('- [OK] All conditions appear to be met');
    }

    await captureScreenshot(page, 'conditions-check-02-final');
  });
});
