// Test script to verify chat input UX improvements
const { chromium } = require('playwright');

async function testChatInputUX() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('Starting chat input UX tests...\n');

  // Navigate to the app
  await page.goto('http://localhost:8000');
  await page.waitForTimeout(1000); // Wait for page load

  // Navigate to chat tab
  await page.keyboard.press('c');
  await page.waitForTimeout(500);

  const results = [];

  // Test 1: Shift+Enter inserts newline
  console.log('Test 1: Shift+Enter inserts newline');
  const textarea = await page.locator('.chat-input-box textarea');
  await textarea.click();
  await textarea.fill('Line 1');
  await page.keyboard.press('Shift+Enter');
  await textarea.type('Line 2');
  const value = await textarea.inputValue();
  const hasNewline = value.includes('\n');
  results.push({ test: 'Shift+Enter newline', passed: hasNewline });
  console.log(`  Shift+Enter inserts newline: ${hasNewline ? 'PASS' : 'FAIL'}`);
  console.log(`  Value: ${JSON.stringify(value)}`);

  // Clear textarea
  await textarea.fill('');

  // Test 2: Enter (without Shift) does NOT insert newline (sends message)
  console.log('\nTest 2: Enter sends message (does not insert newline)');
  await textarea.fill('Test message');
  const valueBefore = await textarea.inputValue();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  const valueAfter = await textarea.inputValue();
  const cleared = valueAfter === '';
  results.push({ test: 'Enter sends message', passed: cleared });
  console.log(`  Enter sends message: ${cleared ? 'PASS' : 'FAIL'}`);

  // Test 3: Inline rendering shows for code blocks
  console.log('\nTest 3: Inline rendering for code blocks');
  await textarea.fill('Here is some code:\n```js\nconst x = 1;\n```');
  await page.waitForTimeout(300);
  let overlayVisible = await page.locator('.chat-input-overlay').isVisible().catch(() => false);
  let hasCodeBlock = false;
  if (overlayVisible) {
    hasCodeBlock = await page.locator('.chat-input-overlay pre code').count().then(c => c > 0);
  }
  results.push({ test: 'Inline rendering for code block', passed: overlayVisible && hasCodeBlock });
  console.log(`  Inline overlay shows for code block: ${overlayVisible && hasCodeBlock ? 'PASS' : 'FAIL'}`);

  // Test 4: Inline rendering shows for inline code
  console.log('\nTest 4: Inline rendering for inline code');
  await textarea.fill('Use `console.log()` to print');
  await page.waitForTimeout(300);
  overlayVisible = await page.locator('.chat-input-overlay').isVisible().catch(() => false);
  let hasInlineCode = false;
  if (overlayVisible) {
    hasInlineCode = await page.locator('.chat-input-overlay code').count().then(c => c > 0);
  }
  results.push({ test: 'Inline rendering for inline code', passed: overlayVisible && hasInlineCode });
  console.log(`  Inline overlay shows for inline code: ${overlayVisible && hasInlineCode ? 'PASS' : 'FAIL'}`);

  // Test 5: Inline rendering shows for bullet lists
  console.log('\nTest 5: Inline rendering for bullet lists');
  await textarea.fill('- Item 1\n- Item 2\n- Item 3');
  await page.waitForTimeout(300);
  overlayVisible = await page.locator('.chat-input-overlay').isVisible().catch(() => false);
  let hasBulletList = false;
  if (overlayVisible) {
    hasBulletList = await page.locator('.chat-input-overlay ul li').count().then(c => c >= 3);
  }
  results.push({ test: 'Inline rendering for bullet list', passed: overlayVisible && hasBulletList });
  console.log(`  Inline overlay shows for bullet list: ${overlayVisible && hasBulletList ? 'PASS' : 'FAIL'}`);

  // Test 6: Inline rendering shows for numbered lists
  console.log('\nTest 6: Inline rendering for numbered lists');
  await textarea.fill('1. First\n2. Second\n3. Third');
  await page.waitForTimeout(300);
  overlayVisible = await page.locator('.chat-input-overlay').isVisible().catch(() => false);
  let hasNumberedList = false;
  if (overlayVisible) {
    hasNumberedList = await page.locator('.chat-input-overlay ol li').count().then(c => c >= 3);
  }
  results.push({ test: 'Inline rendering for numbered list', passed: overlayVisible && hasNumberedList });
  console.log(`  Inline overlay shows for numbered list: ${overlayVisible && hasNumberedList ? 'PASS' : 'FAIL'}`);

  // Test 7: Inline overlay hidden for plain text
  console.log('\nTest 7: Inline overlay hidden for plain text');
  await textarea.fill('Just plain text without any markdown');
  await page.waitForTimeout(300);
  overlayVisible = await page.locator('.chat-input-overlay').isVisible().catch(() => false);
  results.push({ test: 'Overlay hidden for plain text', passed: !overlayVisible });
  console.log(`  Overlay hidden for plain text: ${!overlayVisible ? 'PASS' : 'FAIL'}`);

  // Test 8: Reply cursor focus
  console.log('\nTest 8: Reply button focuses chatbox');

  // First, we need to have some message content to select
  // Since we can't easily inject messages, let's test the focus behavior by simulating it
  // We'll check if the textarea can be programmatically focused
  await textarea.fill('');
  await page.evaluate(() => {
    const chatLog = document.querySelector('.chat-log');
    if (!chatLog) return;

    // Create a fake message element
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg';
    msgDiv.innerHTML = '<div class="msg-body"><div class="msg-content">Test selectable text for reply feature</div></div>';
    chatLog.appendChild(msgDiv);
  });

  await page.waitForTimeout(300);

  // Try to select text in the message (simulate user selection)
  const msgContent = await page.locator('.msg-content').first();
  if (await msgContent.isVisible().catch(() => false)) {
    // Select the text
    await msgContent.click({ clickCount: 3 }); // Triple-click to select all
    await page.waitForTimeout(300);

    // Check if selection tooltip appears
    const tooltipVisible = await page.locator('.selection-tooltip').isVisible().catch(() => false);
    console.log(`  Selection tooltip visible: ${tooltipVisible}`);

    if (tooltipVisible) {
      // Click the Reply button
      const replyBtn = await page.locator('.selection-tooltip button').nth(1);
      await replyBtn.click();
      await page.waitForTimeout(400);

      // Check if textarea is focused
      const isFocused = await page.evaluate(() => {
        const textarea = document.querySelector('.chat-input-box textarea');
        return document.activeElement === textarea;
      });

      // Check if cursor is at the end
      const cursorPos = await page.evaluate(() => {
        const textarea = document.querySelector('.chat-input-box textarea');
        return textarea ? textarea.selectionStart : -1;
      });

      const textLength = await textarea.inputValue().then(v => v.length);
      const cursorAtEnd = cursorPos === textLength;

      results.push({ test: 'Reply focuses textarea', passed: isFocused });
      results.push({ test: 'Reply cursor at end', passed: cursorAtEnd });
      console.log(`  Textarea focused after reply: ${isFocused ? 'PASS' : 'FAIL'}`);
      console.log(`  Cursor at end (pos ${cursorPos}/${textLength}): ${cursorAtEnd ? 'PASS' : 'FAIL'}`);
    } else {
      console.log('  Selection tooltip did not appear - skipping reply test');
      results.push({ test: 'Reply focuses textarea', passed: false });
      results.push({ test: 'Reply cursor at end', passed: false });
    }
  } else {
    console.log('  Could not find message content - skipping reply test');
    results.push({ test: 'Reply focuses textarea', passed: false });
    results.push({ test: 'Reply cursor at end', passed: false });
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  const passed = results.filter(r => r.passed).length;
  const total = results.length;
  console.log(`Total: ${passed}/${total} tests passed`);

  if (passed < total) {
    console.log('\nFailed tests:');
    results.filter(r => !r.passed).forEach(r => {
      console.log(`  - ${r.test}`);
    });
  }

  await browser.close();
  return passed === total;
}

testChatInputUX().then(success => {
  process.exit(success ? 0 : 1);
}).catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
