"""Jupyter Notebook 7 utility helpers.

Helper functions for common Notebook 7 operations in e2e tests.
"""

from playwright.async_api import Page, Locator, expect
import re


async def create_new_notebook(
    page: Page,
    kernel: str = "Python 3",
    timeout: int = 30000
):
    """Create a new notebook with specified kernel from the tree page.

    Assumes page is already on the tree page (/tree).
    Returns the new page object for the created notebook (opens in new tab).

    Args:
        page: Playwright page object (must be on /tree page)
        kernel: Kernel type (default: "Python 3")
        timeout: Timeout in milliseconds

    Returns:
        Page object for the newly created notebook
    """
    # Click the "New" dropdown button (has "New" text inside)
    new_button = page.locator('.jp-DropdownMenu.jp-Toolbar-item').filter(has_text='New')
    await expect(new_button).to_be_visible(timeout=timeout)
    await new_button.click()

    # Wait for dropdown menu to appear
    dropdown_menu = page.locator('.lm-Menu.lm-MenuBar-menu')
    await expect(dropdown_menu).to_be_visible(timeout=timeout)

    # Wait for new page to open when clicking "Notebook" option
    async with page.context.expect_page() as new_page_info:
        # Click on "Notebook" option in the dropdown
        notebook_option = dropdown_menu.locator('.lm-Menu-item').filter(has_text='Notebook')
        await expect(notebook_option).to_be_visible(timeout=timeout)
        await notebook_option.click()

    # Get the new page
    new_page = await new_page_info.value

    # Wait for kernel selection dialog to appear
    kernel_dialog = new_page.locator('.jp-Dialog')
    await expect(kernel_dialog).to_be_visible(timeout=timeout)

    # Select the kernel from the select dropdown in the dialog
    select_element = kernel_dialog.locator('.jp-Dialog-content').locator('select.jp-mod-styled')
    await expect(select_element).to_be_visible(timeout=timeout)

    # Find option containing the kernel name (e.g., "Python 3" matches "Python 3 (ipykernel)")
    options = await select_element.locator('option').all()
    selected_value = None
    for option in options:
        text = await option.text_content()
        if kernel in text:
            selected_value = await option.get_attribute('value')
            break

    if selected_value:
        await select_element.select_option(value=selected_value)

    # Click the "Select" button in the dialog
    select_button = kernel_dialog.locator('button.jp-mod-accept')
    await expect(select_button).to_be_visible(timeout=timeout)
    await select_button.click()

    # Wait for the notebook to be ready (first cell visible)
    await expect(new_page.locator('.jp-Cell.jp-CodeCell')).to_be_visible(timeout=timeout)

    return new_page


async def set_cell_type(
    page: Page,
    index: int,
    cell_type: str,
    timeout: int = 30000
):
    """Change the type of a cell at the specified index.

    Similar to Galata's page.notebook.setCellType functionality.

    Args:
        page: Playwright page object
        index: Cell index (0-based)
        cell_type: Cell type ("code" or "markdown")
        timeout: Timeout in milliseconds
    """
    # Get and select the cell
    cell = await get_cell(page, index, timeout)
    await select_cell(page, index, timeout)

    # Check current cell type
    class_name = await cell.get_attribute('class')
    current_cell_type = "code" if 'jp-CodeCell' in class_name else "markdown"

    # Not change if cell type is same
    if current_cell_type == cell_type:
        return

    # Click cell type toolbar item
    cell_type_toolbar_item = page.locator('.jp-Toolbar-item[data-jp-item-name="cellType"]')
    await cell_type_toolbar_item.click()

    # Change cell type
    selectInput = page.locator('div.jp-Notebook-toolbarCellTypeDropdown select')
    await expect(selectInput).to_be_visible(timeout=timeout)
    await selectInput.select_option(cell_type)


async def set_cell(
    page: Page,
    index: int,
    cell_type: str,
    content: str,
    timeout: int = 30000
):
    """Set the content of a cell at the specified index.

    Similar to Galata's page.notebook.setCell functionality.

    Args:
        page: Playwright page object
        index: Cell index (0-based)
        cell_type: Cell type ("code" or "markdown")
        content: Content to set in the cell
        timeout: Timeout in milliseconds
    """
    # Get the cell
    cell = await get_cell(page, index, timeout)

    # Change cell type if needed
    await set_cell_type(page, index, cell_type, timeout)

    # Click the editor to focus it
    editor = cell.locator('.jp-Cell-inputArea')
    if cell_type == 'markdown':
        await editor.dblclick()
    await editor.click()

    # Clear existing content
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.press('Backspace')

    # Type new content
    # give CodeMirror time to style properly
    await page.keyboard.type(content, delay=100 if cell_type == 'code' else 0)

    # give CodeMirror time to style properly
    if cell_type == 'code':
        await page.wait_for_timeout(500)


async def run_cell(
    page: Page,
    index: int,
    wait_for_output: bool = True,
    timeout: int = 30000
):
    """Execute a cell at the specified index.

    Similar to Galata's page.notebook.runCell functionality.

    Args:
        page: Playwright page object
        index: Cell index (0-based)
        wait_for_output: Wait for cell execution to complete (default: True)
        timeout: Timeout in milliseconds
    """
    # Get and select the cell
    cell = await get_cell(page, index, timeout)
    await select_cell(page, index, timeout)

    # Execute using Shift+Enter
    await page.keyboard.press('Shift+Enter')

    # Wait for execution to complete if requested
    if wait_for_output:
        # Wait for the cell to finish executing
        # The prompt changes from [*] (executing) to [n] (completed)
        prompt = cell.locator('.jp-InputArea-prompt')
        # Wait until the prompt doesn't contain [*]
        await expect(prompt).not_to_contain_text('[*]', timeout=timeout)


async def run(
    page: Page,
    timeout: int = 30000
):
    """Execute all cells in the notebook.

    Similar to Galata's page.notebook.run functionality.
    Uses menu click to trigger "Run All Cells" command.

    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds
    """
    # Click the "Run" menu in the menu bar
    run_menu = page.locator('.lm-MenuBar-itemLabel').filter(has_text=re.compile(r'^Run$'))
    await expect(run_menu).to_be_visible(timeout=timeout)
    await run_menu.click()

    # Click "Run All Cells" in the dropdown menu
    dropdown_menu = page.locator('.lm-Menu.lm-MenuBar-menu')
    await expect(dropdown_menu).to_be_visible(timeout=timeout)
    run_all_item = dropdown_menu.locator('.lm-Menu-item[data-command="runmenu:run-all"]')
    await expect(run_all_item).to_be_visible(timeout=timeout)
    await run_all_item.click()

    # Wait for all cells to finish executing
    # Wait until there are no cells with [*] in their prompts
    cells = page.locator('.jp-Cell')
    cell_count = await cells.count()

    for i in range(cell_count):
        cell = cells.nth(i)
        # Check if it's a code cell
        class_name = await cell.get_attribute('class')
        if 'jp-CodeCell' in class_name:
            prompt = cell.locator('.jp-InputArea-prompt')
            # Wait until the prompt doesn't contain [*]
            await expect(prompt).not_to_contain_text('[*]', timeout=timeout)


async def add_cell(
    page: Page,
    cell_type: str,
    content: str,
    timeout: int = 30000
) -> int:
    """Add a new cell at the end of the notebook.

    Similar to Galata's page.notebook.addCell functionality.
    Selects the last cell and clicks the insert button in the toolbar.

    Args:
        page: Playwright page object
        cell_type: Cell type ("code" or "markdown")
        content: Cell content
        timeout: Timeout in milliseconds

    Returns:
        The index of the newly added cell
    """
    # Get all cells and select the last one
    cells = page.locator('.jp-Cell')
    cell_count = await cells.count()

    if cell_count > 0:
        # Select the last cell
        await select_cell(page, cell_count - 1, timeout)

    # Click the insert button in the toolbar
    insert_button = page.locator('.jp-Toolbar-item[data-jp-item-name="insert"]')
    await expect(insert_button).to_be_visible(timeout=timeout)
    await insert_button.click()

    # Wait for the new cell to be added
    new_cell_count = cell_count + 1
    await expect(cells).to_have_count(new_cell_count, timeout=timeout)

    # Set the cell type and content
    new_cell_index = new_cell_count - 1
    await set_cell(page, new_cell_index, cell_type, content, timeout)

    return new_cell_index


async def get_cell(
    page: Page,
    index: int,
    timeout: int = 30000
) -> Locator:
    """Get the cell element at the specified index.

    Similar to Galata's page.notebook.getCell functionality.

    Args:
        page: Playwright page object
        index: Cell index (0-based)
        timeout: Timeout in milliseconds

    Returns:
        Playwright Locator for the cell element
    """
    cells = page.locator('.jp-Cell')
    cell = cells.nth(index)
    await expect(cell).to_be_visible(timeout=timeout)
    return cell


async def select_cell(
    page: Page,
    index: int,
    timeout: int = 30000
):
    """Select a cell at the specified index.

    Similar to Galata's page.notebook.selectCells functionality.

    Args:
        page: Playwright page object
        index: Cell index (0-based)
        timeout: Timeout in milliseconds
    """
    cell = await get_cell(page, index, timeout)
    await cell.click()


__all__ = [
    "create_new_notebook",
    "set_cell_type",
    "set_cell",
    "run_cell",
    "run",
    "add_cell",
    "get_cell",
    "select_cell",
]
