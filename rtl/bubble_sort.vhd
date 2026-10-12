library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package typedef is

  type vector_vector is array (NATURAL range <>) of std_logic_vector(7 downto 0);

end;


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_unsigned.ALL;
use work.typedef.all;


entity bubble_sort is
  port ( 
    unsorted : in vector_vector(23 downto 0);
    median : out std_logic_vector(7 downto 0)
  );
end bubble_sort;

architecture Behavioral of bubble_sort is

  shared variable ppp : vector_vector(23 downto 0);

begin
 
  process(unsorted)
    variable temp : std_logic_vector(7 downto 0);
  begin
    ppp := unsorted;
    for i in 0 to 23 loop
      for j in 0 to 23-i-1 loop
        if(ppp(j) > ppp(j+1)) then
          temp := ppp(j);
          ppp(j) := ppp(j+1); 
          ppp(j+1) := temp;
        end if;
      end loop;
    end loop;
    median <= ppp(11);
  end process;


end Behavioral;
